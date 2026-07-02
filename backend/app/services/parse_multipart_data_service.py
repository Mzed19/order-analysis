from __future__ import annotations
from io import BytesIO
from app.helpers.text_helper import normalize_extracted_text

def extract_text_from_file(filename: str | None, data: bytes) -> str:
    lower_name = filename.lower() if filename else ""
    if lower_name.endswith(".pdf"):
        from pypdf import PdfReader

        reader = PdfReader(BytesIO(data))
        pages: list[str] = []
        for page in reader.pages:
            try:
                pages.append(page.extract_text() or "")
            except Exception:
                continue
        return normalize_extracted_text("\n\n".join(pages))

    for encoding in ("utf-8", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue

    return data.decode("utf-8", errors="replace")
