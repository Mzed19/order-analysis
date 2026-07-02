from __future__ import annotations

import argparse
from http.server import HTTPServer

from app.controllers.contract_analysis_controller import ContractAnalysisHandler


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
