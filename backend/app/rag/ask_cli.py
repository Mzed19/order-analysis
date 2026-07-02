from __future__ import annotations

import argparse

from app.rag.pipeline import ask


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pergunte ao assistente usando o contexto armazenado na base vetorial."
    )
    parser.add_argument(
        "question",
        help="Pergunta a ser enviada para a função ask",
    )
    args = parser.parse_args()

    response = ask(args.question)
    print(response)


if __name__ == "__main__":
    main()

