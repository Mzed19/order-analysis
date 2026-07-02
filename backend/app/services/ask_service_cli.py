from __future__ import annotations

import argparse
import os
import sys

import requests


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Send a question to the ask service and print the answer."
    )
    parser.add_argument("question", help="Pergunta a ser enviada ao serviço de RAG")
    parser.add_argument("--host", default=os.getenv("ASK_SERVICE_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("ASK_SERVICE_PORT", "8000")))
    parser.add_argument("--timeout", type=int, default=120, help="Timeout em segundos para aguardar resposta")
    args = parser.parse_args()

    url = f"http://{args.host}:{args.port}/ask"

    try:
        response = requests.post(
            url,
            json={"question": args.question},
            timeout=args.timeout,
        )
    except requests.RequestException as exc:
        print(f"Erro ao conectar no serviço: {exc}", file=sys.stderr)
        sys.exit(1)

    if response.status_code != 200:
        body = response.text
        print(f"Serviço retornou {response.status_code}: {body}", file=sys.stderr)
        sys.exit(1)

    payload = response.json()
    answer = payload.get("answer")
    if answer is None:
        print(f"Resposta inválida do serviço: {payload}", file=sys.stderr)
        sys.exit(1)

    print(answer)


if __name__ == "__main__":
    main()
