from __future__ import annotations

import argparse
from pathlib import Path

from app.core.google_page_rag_scraper import chunk_text, normalize_text


def extract_pdf_text(file_path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(file_path)
    pages: list[str] = []

    for page_number, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""

        if text.strip():
            pages.append(text)

    return normalize_text("\n\n".join(pages))


def resolve_title(file_path: Path, text: str | None = None) -> str:
    try:
        from pypdf import PdfReader

        reader = PdfReader(file_path)
        metadata = reader.metadata
        if metadata and getattr(metadata, "title", None):
            title = str(metadata.title).strip()
            if title:
                return title
    except Exception:
        pass

    title_from_name = file_path.stem.replace("_", " ").replace("-", " ").strip()
    return title_from_name or str(file_path)


def resolve_source(file_path: Path) -> str:
    name = file_path.name
    return f"pdf_file:{name}"


def ingest_pdf_file(
    file_path: str,
    title: str | None = None,
    source: str | None = None,
    chunk_size: int = 700,
    overlap: int = 100,
    dry_run: bool = False,
) -> list[str]:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {file_path}")
    if path.is_dir():
        raise ValueError(f"Expected a PDF file path, but got a directory: {file_path}")

    text = extract_pdf_text(path)
    if not text:
        raise ValueError(f"No text extracted from PDF: {file_path}")

    chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap)
    resolved_title = title or resolve_title(path, text)
    resolved_source = source or resolve_source(path)

    if not dry_run and chunks:
        from app.rag.ingestion.ingest import embedAndStore

        inserted_count = embedAndStore(
            chunks,
            title=resolved_title,
            source=resolved_source,
        )
        print(f"Ingested {inserted_count} new chunks from '{file_path}'.")
    else:
        print(f"Prepared {len(chunks)} chunks from '{file_path}'.")

    return chunks


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest a local PDF file into the RAG vector database."
    )
    parser.add_argument("file_path", help="Local path to the PDF file")
    parser.add_argument("--title", help="Optional document title to store in the database")
    parser.add_argument("--source", help="Optional source label to store in the database")
    parser.add_argument("--chunk-size", type=int, default=700)
    parser.add_argument("--overlap", type=int, default=100)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--preview", type=int, default=3)
    args = parser.parse_args()

    chunks = ingest_pdf_file(
        file_path=args.file_path,
        title=args.title,
        source=args.source,
        chunk_size=args.chunk_size,
        overlap=args.overlap,
        dry_run=args.dry_run,
    )

    action = "Prepared" if args.dry_run else "Ingested"
    print(f"{action} {len(chunks)} PDF chunks.")

    for index, chunk in enumerate(chunks[: args.preview], start=1):
        print(f"\n--- chunk {index} ---")
        print(chunk[:1000])


if __name__ == "__main__":
    main()

