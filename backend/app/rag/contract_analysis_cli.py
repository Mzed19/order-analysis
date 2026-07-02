from __future__ import annotations

import argparse
import os
import sys

import requests


def read_contract_text(path: str) -> str:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")

    lower_path = path.lower()
    if lower_path.endswith(".pdf"):
        from pypdf import PdfReader

        reader = PdfReader(path)
        pages: list[str] = []
        for page in reader.pages:
            try:
                pages.append(page.extract_text() or "")
            except Exception:
                continue
        return "\n\n".join(pages)

    text = None
    for encoding in ("utf-8", "cp1252", "latin-1"):
        try:
            with open(path, "r", encoding=encoding, errors="replace") as file:
                text = file.read()
            break
        except UnicodeDecodeError:
            continue

    if text is None:
        with open(path, "rb") as file:
            raw = file.read()
            text = raw.decode("utf-8", errors="replace")

    return text


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Send a contract text to the analysis service and print the result."
    )
    parser.add_argument(
        "contract",
        help="Contract text or path to a contract file to analyze",
    )
    parser.add_argument("--host", default=os.getenv("ASK_SERVICE_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("ASK_SERVICE_PORT", "8001")))
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()

    send_as_file = os.path.exists(args.contract)
    url = f"http://{args.host}:{args.port}/analyze"

    try:
        if send_as_file:
            with open(args.contract, "rb") as file:
                response = requests.post(
                    url,
                    files={"contract_file": (os.path.basename(args.contract), file)},
                    timeout=args.timeout,
                )
        else:
            if not args.contract.strip():
                print("Contrato vazio. Forneça texto ou caminho válido.", file=sys.stderr)
                sys.exit(1)

            response = requests.post(
                url,
                json={"contract": args.contract},
                timeout=args.timeout,
            )
    except requests.RequestException as exc:
        print(f"Erro ao conectar no serviço: {exc}", file=sys.stderr)
        sys.exit(1)

    if response.status_code != 200:
        print(f"Serviço retornou {response.status_code}: {response.text}", file=sys.stderr)
        sys.exit(1)

    data = response.json()
    analysis = data.get("analysis")
    if analysis is None:
        print(f"Resposta inesperada do serviço: {data}", file=sys.stderr)
        sys.exit(1)

    print(analysis)


if __name__ == "__main__":
    main()
