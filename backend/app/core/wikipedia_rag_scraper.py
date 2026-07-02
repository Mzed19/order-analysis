from __future__ import annotations

import argparse
import json
import logging
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from time import sleep

import requests


LOGGER = logging.getLogger(__name__)

DEFAULT_LANGUAGE = "pt"
DEFAULT_HEADERS = {
    "User-Agent": "finance-document-reader/1.0 (RAG research scraper)",
}


@dataclass(frozen=True)
class WikipediaArticle:
    page_id: int
    title: str
    page_url: str
    text: str
    snippet: str = ""


@dataclass(frozen=True)
class RagChunk:
    text: str
    metadata: dict[str, str | int | None]


class WikipediaRagScraper:
    """
    Search Wikipedia through the public MediaWiki API and build RAG chunks.

    This is a more automation-friendly source than Google Scholar because it
    exposes official JSON endpoints for search and article text extraction.
    """

    def __init__(
        self,
        language: str = DEFAULT_LANGUAGE,
        max_results: int = 5,
        request_timeout: int = 30,
        delay_seconds: float = 0.2,
        max_retries: int = 3,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.language = language
        self.max_results = max_results
        self.request_timeout = request_timeout
        self.delay_seconds = delay_seconds
        self.max_retries = max_retries
        self.api_url = f"https://{language}.wikipedia.org/w/api.php"
        self.session = requests.Session()
        self.session.headers.update(headers or DEFAULT_HEADERS)

    def build_rag_chunks(
        self,
        query: str,
        chunk_size: int = 1200,
        overlap: int = 150,
    ) -> list[RagChunk]:
        chunks: list[RagChunk] = []

        for article in self.scrape_articles(query):
            article_chunks = chunk_text(article.text, chunk_size=chunk_size, overlap=overlap)
            for index, chunk in enumerate(article_chunks, start=1):
                chunks.append(
                    RagChunk(
                        text=chunk,
                        metadata={
                            "title": article.title,
                            "page_id": article.page_id,
                            "page_url": article.page_url,
                            "snippet": article.snippet,
                            "chunk_index": index,
                            "source": f"wikipedia_{self.language}",
                        },
                    )
                )

        return chunks

    def scrape_articles(self, query: str) -> list[WikipediaArticle]:
        articles: list[WikipediaArticle] = []

        for result in self.search(query):
            self._pause()
            text = self.fetch_article_text(result["page_id"])
            if not text:
                LOGGER.info("Skipping article without extractable text: %s", result["title"])
                continue

            articles.append(
                WikipediaArticle(
                    page_id=result["page_id"],
                    title=result["title"],
                    page_url=self.page_url(result["title"]),
                    text=text,
                    snippet=result["snippet"],
                )
            )

            if len(articles) >= self.max_results:
                break

        return articles

    def search(self, query: str) -> list[dict[str, str | int]]:
        results: list[dict[str, str | int]] = []
        offset = 0

        while len(results) < self.max_results:
            batch_size = min(50, self.max_results - len(results))
            response = self._get(
                {
                    "action": "query",
                    "format": "json",
                    "list": "search",
                    "srsearch": query,
                    "srlimit": batch_size,
                    "sroffset": offset,
                    "srwhat": "text",
                    "utf8": 1,
                }
            )

            items = response.get("query", {}).get("search", [])
            if not items:
                break

            for item in items:
                results.append(
                    {
                        "page_id": item["pageid"],
                        "title": item["title"],
                        "snippet": clean_html_snippet(item.get("snippet", "")),
                    }
                )

            next_offset = response.get("continue", {}).get("sroffset")
            if next_offset is None:
                break
            offset = next_offset
            self._pause()

        return results

    def fetch_article_text(self, page_id: int) -> str:
        response = self._get(
            {
                "action": "query",
                "format": "json",
                "prop": "extracts",
                "explaintext": 1,
                "exsectionformat": "plain",
                "pageids": page_id,
                "redirects": 1,
                "utf8": 1,
            }
        )

        page = response.get("query", {}).get("pages", {}).get(str(page_id), {})
        return normalize_text(page.get("extract", ""))

    def page_url(self, title: str) -> str:
        slug = title.replace(" ", "_")
        return f"https://{self.language}.wikipedia.org/wiki/{slug}"

    def _get(self, params: dict[str, str | int]) -> dict:
        for attempt in range(1, self.max_retries + 1):
            response = self.session.get(
                self.api_url,
                params=params,
                timeout=self.request_timeout,
            )

            if response.status_code != 429:
                response.raise_for_status()
                return response.json()

            retry_after = response.headers.get("Retry-After")
            wait_seconds = int(retry_after) if retry_after and retry_after.isdigit() else attempt * 2
            LOGGER.warning("Wikipedia rate limited the request. Retrying in %s seconds.", wait_seconds)
            sleep(wait_seconds)

        response.raise_for_status()
        return response.json()

    def _pause(self) -> None:
        if self.delay_seconds > 0:
            sleep(self.delay_seconds)


def clean_html_snippet(snippet: str) -> str:
    text = re.sub(r"<[^>]+>", "", snippet)
    return normalize_text(text)


def normalize_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"={2,}\s*[^=\n]+\s*={2,}", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def chunk_text(text: str, chunk_size: int = 1200, overlap: int = 150) -> list[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be greater than or equal to zero and smaller than chunk_size")

    chunks: list[str] = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = end - overlap

    return chunks


def write_jsonl(chunks: list[RagChunk], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        for chunk in chunks:
            file.write(json.dumps(asdict(chunk), ensure_ascii=False) + "\n")


def scrape_wikipedia_for_rag(
    query: str,
    language: str = DEFAULT_LANGUAGE,
    max_results: int = 5,
    chunk_size: int = 1200,
    overlap: int = 150,
    delay_seconds: float = 0.2,
) -> list[RagChunk]:
    scraper = WikipediaRagScraper(
        language=language,
        max_results=max_results,
        delay_seconds=delay_seconds,
    )
    return scraper.build_rag_chunks(query=query, chunk_size=chunk_size, overlap=overlap)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Search Wikipedia through MediaWiki API and emit RAG chunks."
    )
    parser.add_argument("query", help="Search text for Wikipedia")
    parser.add_argument("--language", default=DEFAULT_LANGUAGE)
    parser.add_argument("--max-results", type=int, default=5)
    parser.add_argument("--chunk-size", type=int, default=1200)
    parser.add_argument("--overlap", type=int, default=150)
    parser.add_argument("--delay-seconds", type=float, default=0.2)
    parser.add_argument("--output", type=Path, help="Optional JSONL output path")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s:%(name)s:%(message)s",
    )

    chunks = scrape_wikipedia_for_rag(
        query=args.query,
        language=args.language,
        max_results=args.max_results,
        chunk_size=args.chunk_size,
        overlap=args.overlap,
        delay_seconds=args.delay_seconds,
    )

    if args.output:
        write_jsonl(chunks, args.output)
        print(f"Wrote {len(chunks)} chunks to {args.output}")
        return

    for chunk in chunks:
        print(json.dumps(asdict(chunk), ensure_ascii=False))


if __name__ == "__main__":
    main()
