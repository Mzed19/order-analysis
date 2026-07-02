from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from app.rag.pipeline import ask


class AskRequestHandler(BaseHTTPRequestHandler):
    def _send_json(self, status_code: int, data: dict[str, Any]) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        if self.path != "/ask":
            self._send_json(404, {"error": "Endpoint not found"})
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            payload = json.loads(body.decode("utf-8"))
            question = payload.get("question")
            if not question or not isinstance(question, str):
                raise ValueError("Missing or invalid 'question' field")
        except Exception as exc:
            self._send_json(400, {"error": str(exc)})
            return

        try:
            answer = ask(question)
        except Exception as exc:
            self._send_json(500, {"error": str(exc)})
            return

        self._send_json(200, {"answer": answer})

def serve(host: str = "0.0.0.0", port: int = 8000) -> None:
    server = HTTPServer((host, port), AskRequestHandler)
    print(f"Ask service running at http://{host}:{port} (endpoint /ask)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Shutting down ask service...")
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the RAG ask service and keep the model loaded in memory."
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind the ask service")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on")
    args = parser.parse_args()

    serve(host=args.host, port=args.port)


if __name__ == "__main__":
    main()

