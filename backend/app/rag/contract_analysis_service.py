from __future__ import annotations

import argparse
import json
import re
from http.server import BaseHTTPRequestHandler, HTTPServer
from io import BytesIO
from typing import Any
from urllib.parse import urlparse
from app.helpers.text_helper import normalize_extracted_text
import numpy as np
from app.core.embeddings import embed_passages, embed_query
from app.core.google_page_rag_scraper import chunk_text, normalize_text
from app.workers.task_queue import enqueue_task, get_task, task_exists, get_task
from app.core.redis_cache import make_contract_cache_key, get_contract_chunks, set_contract_chunks
from app.rag.pipeline import generate_response

from app.services.analyze_contract_service import (
    ANALYSIS_QUERY,
    SYSTEM_MESSAGE,
    build_analysis_prompt_for_context,
)

CHUNK_SIZE = 800
OVERLAP = 150
MAX_CHUNKS = 12


def build_chunks(contract_text: str) -> list[dict[str, Any]]:
    normalized = normalize_text(contract_text)
    chunks = chunk_text(normalized, chunk_size=CHUNK_SIZE, overlap=OVERLAP)
    if not chunks:
        raise ValueError("Não foi possível extrair trechos do contrato fornecido.")

    embeddings = embed_passages(chunks)
    return [
        {
            "text": chunk,
            "embedding": emb.tolist(),
        }
        for chunk, emb in zip(chunks, embeddings)
    ]


def get_or_create_chunks(contract_text: str, filename: str | None = None) -> list[dict[str, Any]]:
    cache_key = make_contract_cache_key(contract_text, filename)
    chunks = get_contract_chunks(cache_key)
    if chunks:
        return chunks

    chunks = build_chunks(contract_text)
    set_contract_chunks(cache_key, chunks)
    return chunks


def cosine_similarity(query: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    query_norm = np.linalg.norm(query)
    matrix_norm = np.linalg.norm(matrix, axis=1)
    if query_norm == 0 or np.any(matrix_norm == 0):
        return np.zeros(matrix.shape[0], dtype=float)
    return (matrix @ query) / (query_norm * matrix_norm)


def select_relevant_chunks(chunks: list[dict[str, Any]]) -> list[str]:
    query_embedding = embed_query([ANALYSIS_QUERY])[0]
    matrix = np.array([chunk["embedding"] for chunk in chunks], dtype="float32")
    scores = cosine_similarity(query_embedding, matrix)
    top_indices = list(np.argsort(scores)[-MAX_CHUNKS:][::-1])
    return [chunks[i]["text"] for i in top_indices if scores[i] > 0.1]


# Prompt configuration imported from app.services.analyze_contract_service


def analyze_contract(contract_text: str, filename: str | None = None) -> list[str]:
    print(f"Analisando contrato: filename={filename}, texto[:200]={contract_text[:200]}...")
    chunks = get_or_create_chunks(contract_text, filename)
    relevant_chunks = select_relevant_chunks(chunks)
    print(f"Chunks relevantes encontrados: {len(relevant_chunks)}")
    if not relevant_chunks:
        raise ValueError("Não foram encontrados trechos relevantes para análise.")

    # Consolidar todos os trechos relevantes em um único contexto para evitar redundância
    combined_context = "\n\n".join(relevant_chunks)

    print("Analisando contexto consolidado do pedido de compra...")
    prompt = build_analysis_prompt_for_context(combined_context)
    messages = [SYSTEM_MESSAGE, {"role": "user", "content": prompt}]
    analysis = generate_response(messages)

    return [analysis]


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


def parse_multipart_form_data(body: bytes, content_type: str) -> dict[str, tuple[bytes | str, str | None]]:
    boundary_match = re.search(r"boundary=(?P<boundary>.+)", content_type)
    if not boundary_match:
        raise ValueError("Boundary não encontrado em multipart/form-data.")

    boundary = boundary_match.group("boundary").strip()
    if boundary.startswith('"') and boundary.endswith('"'):
        boundary = boundary[1:-1]

    boundary_bytes = boundary.encode("latin-1")
    parts = body.split(b"--" + boundary_bytes)

    fields: dict[str, tuple[bytes | str, str | None]] = {}
    for part in parts:
        part = part.strip(b"\r\n")
        if not part or part == b"--":
            continue

        header_data, _, value = part.partition(b"\r\n\r\n")
        if not value:
            continue

        headers = {}
        for header_line in header_data.split(b"\r\n"):
            header_text = header_line.decode("latin-1", errors="replace")
            if ":" not in header_text:
                continue
            name, val = header_text.split(":", 1)
            headers[name.strip().lower()] = val.strip()

        content_disposition = headers.get("content-disposition", "")
        disposition_parts = [item.strip() for item in content_disposition.split(";") if item.strip()]
        disposition_data = {}
        for item in disposition_parts[1:]:
            if "=" in item:
                key, val = item.split("=", 1)
                disposition_data[key.strip().lower()] = val.strip().strip('"')

        field_name = disposition_data.get("name")
        filename = disposition_data.get("filename")
        if not field_name:
            continue

        value = value.rstrip(b"\r\n")
        if filename:
            fields[field_name] = (value, filename)
        else:
            fields[field_name] = (value.decode("utf-8", errors="replace"), None)

    return fields


def parse_contract_request(self) -> tuple[str, str | None]:
    content_type = self.headers.get("Content-Type", "")
    content_length = int(self.headers.get("Content-Length", 0))
    body = self.rfile.read(content_length)

    filename = None

    if content_type.startswith("multipart/form-data"):
        fields = parse_multipart_form_data(body, content_type)

        if "contract_file" in fields:
            file_data, fname = fields["contract_file"]
            if isinstance(file_data, bytes):
                filename = fname
                return extract_text_from_file(filename, file_data), filename
            raise ValueError("contract_file deve ser enviado como arquivo.")

        if "contract" in fields:
            contract_text, _ = fields["contract"]
            return str(contract_text), filename

        raise ValueError("O campo 'contract_file' ou 'contract' é obrigatório.")

    if "application/json" in content_type:
        if not body.strip():
            raise ValueError("Corpo JSON vazio.")
        try:
            payload = json.loads(body.decode("utf-8", errors="replace"))
        except json.JSONDecodeError as exc:
            raise ValueError("JSON inválido no corpo da requisição.") from exc
        contract_text = payload.get("contract")
        if not contract_text or not isinstance(contract_text, str):
            raise ValueError("O campo 'contract' é obrigatório e deve ser uma string.")
        return contract_text, filename

    if not content_type:
        if not body.strip():
            raise ValueError("Nenhum conteúdo enviado.")
        decoded_body = body.decode("utf-8", errors="replace")
        stripped_body = decoded_body.strip()
        if stripped_body.startswith("{"):
            try:
                payload = json.loads(stripped_body)
            except json.JSONDecodeError as exc:
                raise ValueError("JSON inválido no corpo da requisição.") from exc
            contract_text = payload.get("contract")
            if not contract_text or not isinstance(contract_text, str):
                raise ValueError("O campo 'contract' é obrigatório e deve ser uma string.")
            return contract_text, filename
        return decoded_body, filename

    if content_type.startswith("text/"):
        return body.decode("utf-8", errors="replace"), filename

    raise ValueError("Content-Type inválido. Use application/json ou multipart/form-data.")


class ContractAnalysisHandler(BaseHTTPRequestHandler):
    def _send_json(self, status_code: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/analyze":
            try:
                contract_text, filename = parse_contract_request(self)
            except Exception as exc:
                self._send_json(400, {"error": str(exc)})
                return

            task_id = enqueue_task(contract_text, filename)

            self._send_json(202, {"task_id": task_id, "status": "pending"})
        else:
            self._send_json(404, {"error": "Endpoint not found"})

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path.startswith("/analyze/"):
            task_id = path[len("/analyze/"):]
            if not task_id:
                self._send_json(400, {"error": "Task ID required"})
                return
            
            if not task_exists(task_id):
                self._send_json(404, {"error": f"Task {task_id} not found"})
                return

            self._send_json(200, get_task(task_id))
        else:
            self._send_json(404, {"error": "Endpoint not found"})

    def log_message(self, format: str, *args: Any) -> None:
        return


def serve(host: str = "0.0.0.0", port: int = 8001) -> None:
    server = HTTPServer((host, port), ContractAnalysisHandler)
    print(f"Contract analysis service running at http://{host}:{port}/analyze")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Shutting down contract analysis service...")
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the contract analysis service and cache contract chunks in Redis."
    )
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()
    serve(host=args.host, port=args.port)


if __name__ == "__main__":
    main()

