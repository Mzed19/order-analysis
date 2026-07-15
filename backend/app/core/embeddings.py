import os

from sentence_transformers import SentenceTransformer
import numpy as np
from pathlib import Path

EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "768"))

current_file_path = Path(__file__).resolve()
BASE_DIR = current_file_path.parent.parent.parent
MODEL_PATH = os.path.join(BASE_DIR, "models", os.getenv("EMBEDDING_MODEL_NAME", "multilingual-e5-base"))

model = SentenceTransformer(MODEL_PATH)
print(f"Modelo de embeddings carregado: {MODEL_PATH}")

def embed(texts: list[str], input_type: str = "passage") -> np.ndarray:
    prefixed_texts = prefix_texts(texts, input_type=input_type)
    embeddings = model.encode(prefixed_texts)
    print(len(embeddings), "generated embeddings")
    return np.array(embeddings).astype('float32')


def embed_query(texts: list[str]) -> np.ndarray:
    return embed(texts, input_type="query")


def embed_passages(texts: list[str]) -> np.ndarray:
    return embed(texts, input_type="passage")


def prefix_texts(texts: list[str], input_type: str) -> list[str]:
    if input_type not in {"query", "passage"}:
        raise ValueError("input_type must be 'query' or 'passage'")

    prefix = f"{input_type}: "
    return [
        text if text.strip().lower().startswith(prefix) else f"{prefix}{text}"
        for text in texts
    ]
