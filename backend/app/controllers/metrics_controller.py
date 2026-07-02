import json
from http.server import BaseHTTPRequestHandler
from infra.database.postgres import get_conn, release_conn
from app.helpers.auth_helper import validate_token
from urllib.parse import urlparse

class MetricsHandler(BaseHTTPRequestHandler):
    def _send_json(self, status_code: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_GET(self):
        auth_header = self.headers.get("Authorization")
        if not auth_header or not validate_token(auth_header):
            self._send_json(401, {"error": "Unauthorized"})
            return

        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT user_name, document_name, analyzed_at FROM metrics ORDER BY analyzed_at DESC")
                rows = cur.fetchall()
                metrics = [
                    {
                        "user_name": row[0],
                        "document_name": row[1],
                        "analyzed_at": row[2].isoformat() if row[2] else None
                    }
                    for row in rows
                ]
                self._send_json(200, {"metrics": metrics})
        except Exception as e:
            self._send_json(500, {"error": str(e)})
        finally:
            release_conn(conn)
