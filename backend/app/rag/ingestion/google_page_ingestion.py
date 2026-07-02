from __future__ import annotations

import argparse
from urllib.parse import urlparse

from app.core.google_page_rag_scraper import normalize_google_url, scrape_google_page_for_rag


def ingest_google_page(
    url: str,
    title: str | None = None,
    source: str | None = None,
    chunk_size: int = 700,
    overlap: int = 100,
    delay_seconds: float = 0.5,
    request_timeout: int = 30,
    dry_run: bool = False,
) -> list[str]:
    normalized_url = normalize_google_url(url)
    rag_chunks = scrape_google_page_for_rag(
        url=normalized_url,
        chunk_size=chunk_size,
        overlap=overlap,
        delay_seconds=delay_seconds,
        request_timeout=request_timeout,
    )
    texts = [chunk.text for chunk in rag_chunks]

    resolved_title = title or resolve_title(rag_chunks, normalized_url)
    resolved_source = source or resolve_source(normalized_url)

    if not dry_run and texts:
        from app.rag.ingestion.ingest import embedAndStore

        inserted_count = embedAndStore(
            texts,
            title=resolved_title,
            source=resolved_source,
        )
        print(f"Ingested {inserted_count} new chunks from '{normalized_url}'.")
    else:
        print(f"Prepared {len(texts)} chunks from '{normalized_url}'.")

    return texts


def resolve_title(rag_chunks, fallback_url: str) -> str:
    if rag_chunks:
        title = rag_chunks[0].metadata.get("title")
        if title:
            return str(title)
    return fallback_url


def resolve_source(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return f"google_page:{host}" if host else "google_page"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest a Google result URL or public page into the RAG vector database."
    )
    parser.add_argument("url", help="URL copied from Google or a public page URL")
    parser.add_argument("--title", help="Optional document title to store in the database")
    parser.add_argument("--source", help="Optional source label to store in the database")
    parser.add_argument("--chunk-size", type=int, default=700)
    parser.add_argument("--overlap", type=int, default=100)
    parser.add_argument("--delay-seconds", type=float, default=0.5)
    parser.add_argument("--request-timeout", type=int, default=30)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--preview", type=int, default=3)
    args = parser.parse_args()

    chunks = ingest_google_page(
        url=args.url,
        title=args.title,
        source=args.source,
        chunk_size=args.chunk_size,
        overlap=args.overlap,
        delay_seconds=args.delay_seconds,
        request_timeout=args.request_timeout,
        dry_run=args.dry_run,
    )

    action = "Prepared" if args.dry_run else "Ingested"
    print(f"{action} {len(chunks)} Google page chunks.")

    for index, chunk in enumerate(chunks[: args.preview], start=1):
        print(f"\n--- chunk {index} ---")
        print(chunk[:1000])


if __name__ == "__main__":
    main()

