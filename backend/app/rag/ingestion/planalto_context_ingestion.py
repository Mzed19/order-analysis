from __future__ import annotations

import argparse
from dataclasses import dataclass
from time import sleep

from app.core.planalto_rag_scraper import discover_planalto_document_links, scrape_planalto_for_rag


@dataclass(frozen=True)
class PlanaltoSource:
    label: str
    title: str
    url: str
    is_index: bool = False


PLANALTO_SOURCES = [
    PlanaltoSource(
        label="constituicao",
        title="Constituição da República Federativa do Brasil",
        url="https://www.planalto.gov.br/ccivil_03/Constituicao/constituicao.htm",
    ),
    PlanaltoSource(
        label="leis_principais",
        title="Índice de leis principais do Planalto",
        url="https://www.planalto.gov.br/ccivil_03/leis/_lei-principal.htm",
        is_index=True,
    ),
]


def ingest_planalto_context(
    chunk_size: int = 900,
    overlap: int = 120,
    delay_seconds: float = 2.0,
    request_timeout: int = 90,
    max_chunks_per_source: int | None = None,
    max_index_links: int | None = None,
    dry_run: bool = False,
) -> list[str]:
    all_chunks: list[str] = []

    expanded_sources = expand_planalto_sources(
        sources=PLANALTO_SOURCES,
        max_index_links=max_index_links,
        delay_seconds=delay_seconds,
        request_timeout=request_timeout,
    )

    for source in expanded_sources:
        try:
            rag_chunks = scrape_planalto_for_rag(
                urls=[source.url],
                chunk_size=chunk_size,
                overlap=overlap,
                delay_seconds=delay_seconds,
                request_timeout=request_timeout,
            )
        except Exception as exc:
            print(f"Skipping Planalto source '{source.label}' after fetch error: {exc}")
            sleep(delay_seconds)
            continue

        texts = [chunk.text for chunk in rag_chunks]
        if max_chunks_per_source is not None:
            texts = texts[:max_chunks_per_source]

        all_chunks.extend(texts)

        if not dry_run and texts:
            from app.rag.ingestion.ingest import embedAndStore

            inserted_count = embedAndStore(
                texts,
                title=source.title,
                source=f"planalto_{source.label}",
            )
            print(f"Ingested {inserted_count} new chunks for Planalto source '{source.label}'.")
        else:
            print(f"Prepared {len(texts)} chunks for Planalto source '{source.label}'.")

        sleep(delay_seconds)

    return all_chunks


def expand_planalto_sources(
    sources: list[PlanaltoSource],
    max_index_links: int | None,
    delay_seconds: float,
    request_timeout: int,
) -> list[PlanaltoSource]:
    expanded: list[PlanaltoSource] = []
    seen_urls: set[str] = set()

    for source in sources:
        if not source.is_index:
            if source.url not in seen_urls:
                seen_urls.add(source.url)
                expanded.append(source)
            continue

        try:
            links = discover_planalto_document_links(
                index_url=source.url,
                max_links=max_index_links,
                delay_seconds=delay_seconds,
                request_timeout=request_timeout,
            )
        except Exception as exc:
            print(f"Skipping Planalto index '{source.label}' after fetch error: {exc}")
            continue

        print(f"Discovered {len(links)} links from Planalto index '{source.label}'.")
        for index, url in enumerate(links, start=1):
            if url in seen_urls:
                continue
            seen_urls.add(url)
            expanded.append(
                PlanaltoSource(
                    label=f"{source.label}_{index}",
                    title=f"{source.title} - documento {index}",
                    url=url,
                )
            )

        sleep(delay_seconds)

    return expanded


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest planalto.gov.br legal context chunks into the RAG vector database."
    )
    parser.add_argument("--chunk-size", type=int, default=900)
    parser.add_argument("--overlap", type=int, default=120)
    parser.add_argument("--delay-seconds", type=float, default=2.0)
    parser.add_argument("--request-timeout", type=int, default=90)
    parser.add_argument("--max-chunks-per-source", type=int)
    parser.add_argument(
        "--max-index-links",
        type=int,
        help="Limit links discovered from the Planalto law index. Default ingests every link found.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--preview", type=int, default=3)
    args = parser.parse_args()

    chunks = ingest_planalto_context(
        chunk_size=args.chunk_size,
        overlap=args.overlap,
        delay_seconds=args.delay_seconds,
        request_timeout=args.request_timeout,
        max_chunks_per_source=args.max_chunks_per_source,
        max_index_links=args.max_index_links,
        dry_run=args.dry_run,
    )

    action = "Prepared" if args.dry_run else "Ingested"
    print(f"{action} {len(chunks)} Planalto context chunks.")

    for index, chunk in enumerate(chunks[: args.preview], start=1):
        print(f"\n--- chunk {index} ---")
        print(chunk[:1000])


if __name__ == "__main__":
    main()

