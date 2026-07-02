from __future__ import annotations

import argparse
import json
import logging
import re
from dataclasses import asdict, dataclass
from io import BytesIO
from pathlib import Path
from time import sleep
from urllib.parse import parse_qs, unquote, urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader


LOGGER = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}


@dataclass(frozen=True)
class WebPageDocument:
    title: str
    url: str
    text: str
    content_type: str


@dataclass(frozen=True)
class RagChunk:
    text: str
    metadata: dict[str, str | int | None]


class GooglePageRagScraper:
    """
    Fetch a URL copied from Google results or a regular public page and build
    RAG chunks from the page text.
    """

    def __init__(
        self,
        request_timeout: int = 30,
        delay_seconds: float = 0.5,
        max_retries: int = 3,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.request_timeout = request_timeout
        self.delay_seconds = delay_seconds
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update(headers or DEFAULT_HEADERS)

    def build_rag_chunks(
        self,
        url: str,
        chunk_size: int = 700,
        overlap: int = 100,
    ) -> list[RagChunk]:
        document = self.fetch_document(url)
        chunks: list[RagChunk] = []

        for index, chunk in enumerate(chunk_text(document.text, chunk_size, overlap), start=1):
            chunks.append(
                RagChunk(
                    text=chunk,
                    metadata={
                        "title": document.title,
                        "page_url": document.url,
                        "content_type": document.content_type,
                        "chunk_index": index,
                        "source": "google_page",
                    },
                )
            )

        return chunks

    def fetch_document(self, url: str) -> WebPageDocument:
        target_url = normalize_google_url(url)
        validate_url(target_url)

        response = self._get(target_url)
        content_type = response.headers.get("content-type", "").lower()

        if is_pdf_response(target_url, content_type):
            text = extract_pdf_text(response.content)
            title = title_from_url(response.url)
        else:
            response.encoding = response.apparent_encoding or response.encoding
            title, text = extract_html_document(response.text, response.url)

        if not text:
            raise ValueError(f"No extractable text found at URL: {target_url}")

        return WebPageDocument(
            title=title,
            url=response.url,
            text=text,
            content_type=content_type or "unknown",
        )

    def _get(self, url: str) -> requests.Response:
        last_exception: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.session.get(
                    url,
                    timeout=self.request_timeout,
                    allow_redirects=True,
                )
                response.raise_for_status()
                return response
            except requests.RequestException as exc:
                last_exception = exc
                if attempt >= self.max_retries:
                    break

                wait_seconds = self.delay_seconds * attempt
                LOGGER.warning("Request failed for %s. Retrying in %s seconds.", url, wait_seconds)
                sleep(wait_seconds)

        raise last_exception or RuntimeError(f"Could not fetch URL: {url}")


def normalize_google_url(url: str) -> str:
    normalized, _fragment = urldefrag(url.strip())
    parsed = urlparse(normalized)

    if parsed.netloc.lower().endswith("google.com") and parsed.path == "/url":
        query = parse_qs(parsed.query)
        target = query.get("q") or query.get("url")
        if target:
            return unquote(target[0])

    return normalized


def validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"Invalid URL scheme: {url}")
    if not parsed.netloc:
        raise ValueError(f"Invalid URL: {url}")


def is_pdf_response(url: str, content_type: str) -> bool:
    parsed = urlparse(url.lower())
    return "application/pdf" in content_type or parsed.path.endswith(".pdf")


def extract_pdf_text(content: bytes) -> str:
    reader = PdfReader(BytesIO(content))
    pages: list[str] = []

    for page_number, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as exc:
            LOGGER.info("Could not extract PDF page %s: %s", page_number, exc)
            text = ""

        if text.strip():
            pages.append(text)

    return normalize_text("\n\n".join(pages))


def extract_html_document(html: str, base_url: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")

    for node in soup(["script", "style", "noscript", "svg", "canvas", "meta", "link", "nav", "footer", "form"]):
        node.decompose()

    title = extract_title(soup, fallback=title_from_url(base_url))
    text_blocks = extract_text_blocks(soup)
    body_text = extract_body_text(soup)

    if is_google_search_page(base_url):
        text_blocks.extend(extract_google_search_blocks(soup, base_url))

    extracted_text = normalize_text("\n\n".join(text_blocks))
    if should_use_body_fallback(extracted_text, body_text):
        extracted_text = body_text

    return title, extracted_text


def should_use_body_fallback(extracted_text: str, body_text: str) -> bool:
    if not body_text:
        return False
    if not extracted_text:
        return True
    return len(body_text) >= 2 * len(extracted_text) and len(body_text) - len(extracted_text) > 1200


def extract_body_text(soup: BeautifulSoup) -> str:
    root = soup.body or soup
    return normalize_text(root.get_text("\n", strip=True))


def append_unique_block(blocks: list[str], seen: set[str], text: str) -> None:
    text = normalize_inline_text(text)
    if not is_relevant_text(text):
        return

    key = text.lower()
    if key in seen:
        return

    seen.add(key)
    blocks.append(text)


def extract_title(soup: BeautifulSoup, fallback: str) -> str:
    for selector in ("main h1", "article h1", "h1", "title"):
        node = soup.select_one(selector)
        if not node:
            continue
        title = normalize_inline_text(node.get_text(" ", strip=True))
        if title:
            return title
    return fallback


def extract_text_blocks(soup: BeautifulSoup) -> list[str]:
    candidates = soup.select("main, article")
    roots = candidates if candidates else [soup.body or soup]
    blocks: list[str] = []
    seen: set[str] = set()

    for root in roots:
        for node in root.find_all(["h1", "h2", "h3", "h4", "p", "li", "td", "th", "blockquote", "pre"]):
            if has_block_parent(node):
                continue

            append_unique_block(blocks, seen, node.get_text(" ", strip=True))

        if len("\n".join(blocks)) < 2000:
            for node in root.find_all(["section", "div"]):
                if has_rich_text_children(node):
                    continue

                append_unique_block(blocks, seen, node.get_text(" ", strip=True))

    return blocks


def extract_google_search_blocks(soup: BeautifulSoup, base_url: str) -> list[str]:
    blocks: list[str] = []
    seen: set[str] = set()

    for anchor in soup.select("a[href]"):
        heading = anchor.find("h3")
        if not heading:
            continue

        href = normalize_google_url(urljoin(base_url, anchor.get("href", "")))
        title = normalize_inline_text(heading.get_text(" ", strip=True))
        if not title or not href:
            continue

        parent_text = normalize_inline_text(anchor.parent.get_text(" ", strip=True) if anchor.parent else "")
        block = f"{title}\n{href}\n{parent_text}".strip()
        key = block.lower()
        if key in seen:
            continue
        seen.add(key)
        blocks.append(block)

    return blocks


def has_block_parent(node) -> bool:
    parent = node.parent
    while parent is not None:
        if getattr(parent, "name", None) in {"p", "li", "td", "th", "blockquote"}:
            return True
        parent = parent.parent
    return False


def has_rich_text_children(node) -> bool:
    return bool(node.find(["h1", "h2", "h3", "h4", "p", "li", "td", "th", "blockquote", "pre"]))


def is_google_search_page(url: str) -> bool:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    return host.endswith("google.com") and parsed.path in {"", "/", "/search"}


def is_relevant_text(text: str) -> bool:
    if len(text) < 40:
        return False

    lower = text.lower()
    ignored_fragments = (
        "accept cookies",
        "aceitar cookies",
        "política de privacidade",
        "privacy policy",
        "terms of service",
        "todos os direitos reservados",
    )
    return not any(fragment in lower for fragment in ignored_fragments)


def normalize_inline_text(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = text.replace("\x00", " ")
    return re.sub(r"\s+", " ", text).strip()


def normalize_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def title_from_url(url: str) -> str:
    parsed = urlparse(url)
    name = Path(parsed.path).name or parsed.netloc
    return unquote(name).replace("-", " ").replace("_", " ").strip() or url


def chunk_text(text: str, chunk_size: int = 1200, overlap: int = 150) -> list[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be greater than or equal to zero and smaller than chunk_size")

    normalized = normalize_text(text)
    if not normalized:
        return []

    chunks: list[str] = []
    start = 0

    while start < len(normalized):
        end = start + chunk_size
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(normalized):
            break
        start = end - overlap

    return chunks


def write_jsonl(chunks: list[RagChunk], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        for chunk in chunks:
            file.write(json.dumps(asdict(chunk), ensure_ascii=False) + "\n")


def scrape_google_page_for_rag(
    url: str,
    chunk_size: int = 700,
    overlap: int = 100,
    delay_seconds: float = 0.5,
    request_timeout: int = 30,
) -> list[RagChunk]:
    scraper = GooglePageRagScraper(
        delay_seconds=delay_seconds,
        request_timeout=request_timeout,
    )
    return scraper.build_rag_chunks(url=url, chunk_size=chunk_size, overlap=overlap)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch a Google result URL or public page and emit RAG chunks."
    )
    parser.add_argument("url", help="URL copied from Google or a public page URL")
    parser.add_argument("--chunk-size", type=int, default=700)
    parser.add_argument("--overlap", type=int, default=100)
    parser.add_argument("--delay-seconds", type=float, default=0.5)
    parser.add_argument("--request-timeout", type=int, default=30)
    parser.add_argument("--output", type=Path, help="Optional JSONL output path")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s:%(name)s:%(message)s",
    )

    chunks = scrape_google_page_for_rag(
        url=args.url,
        chunk_size=args.chunk_size,
        overlap=args.overlap,
        delay_seconds=args.delay_seconds,
        request_timeout=args.request_timeout,
    )

    if args.output:
        write_jsonl(chunks, args.output)
        print(f"Wrote {len(chunks)} chunks to {args.output}")
        return

    for chunk in chunks:
        print(json.dumps(asdict(chunk), ensure_ascii=False))


if __name__ == "__main__":
    main()
