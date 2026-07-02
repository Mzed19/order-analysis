from __future__ import annotations
import json
import re
from http.server import BaseHTTPRequestHandler
from app.services.parse_multipart_data_service import extract_text_from_file
from typing import Any
from urllib.parse import urlparse
from app.workers.task_queue import enqueue_task, get_task, task_exists, list_tasks, delete_task
from app.helpers.auth_helper import validate_token
from infra.database.postgres import get_conn, release_conn

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

        file_field = fields.get("contract_file") or fields.get("file")
        if file_field:
            file_data, fname = file_field
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
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_error(self, code: int, message: str | None = None, explain: str | None = None) -> None:
        if message is None:
            message = self.responses.get(code, ("", ""))[0]
        self._send_json(code, {"error": message})

    def _authenticate(self) -> bool:
        auth_header = self.headers.get("Authorization")
        if not auth_header:
            self._send_json(401, {"error": "Missing Authorization header"})
            return False
        
        user_info = validate_token(auth_header)
        if not user_info:
            self._send_json(401, {"error": "Invalid or expired token"})
            return False
        
        self.user = user_info
        return True

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_POST(self) -> None:
        if not self._authenticate():
            return

        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/analyze":
            try:
                contract_text, filename = parse_contract_request(self)
            except Exception as exc:
                self._send_json(400, {"error": str(exc)})
                return

            user_id = self.user.get("sub")
            user_name = self.user.get("name") or self.user.get("preferred_username") or "Usuário Desconhecido"
            task_id = enqueue_task(contract_text, filename, user_id, user_name)
            task_data = get_task(task_id, user_id)
            self._send_json(202, task_data)
        else:
            self._send_json(404, {"error": "Endpoint not found"})

    def do_GET(self) -> None:
        if not self._authenticate():
            return

        parsed = urlparse(self.path)
        path = parsed.path.rstrip('/')
        if path == "/analyses":
            user_id = self.user.get("sub")
            tasks = list_tasks(user_id)
            self._send_json(200, {"analyses": tasks})
            return

        if path.startswith("/analyze"):
            task_id = path[len("/analyze/"):]
            if not task_id:
                self._send_json(400, {"error": "Task ID required"})
                return
            
            user_id = self.user.get("sub")
            task_data = get_task(task_id, user_id)
            if task_data is None:
                # Se não existir ou não pertencer ao usuário logado, retornamos 404
                self._send_json(404, {"error": f"Task {task_id} not found"})
                return

            self._send_json(200, {"task": task_data})
            return
        self._send_json(404, {"error": "Endpoint not found"})

    def do_DELETE(self) -> None:
        if not self._authenticate():
            return

        parsed = urlparse(self.path)
        path = parsed.path.rstrip('/')
        if path.startswith("/analyze"):
            task_id = path[len("/analyze/"):]
            if not task_id:
                self._send_json(400, {"error": "Task ID required"})
                return
            
            user_id = self.user.get("sub")
            if delete_task(task_id, user_id):
                self._send_json(200, {"message": "Task deleted successfully"})
            else:
                self._send_json(404, {"error": "Task not found or unauthorized"})
            return

        self._send_json(404, {"error": "Endpoint not found"})
