from app.core.embeddings import embed_passages
from app.core.vector_store import normalize_content, vector_store

# Inicializa o vetor de armazenamento FAISS

def embedAndStore(texts: list[str], title=None, source=None):
    existing = vector_store.existing_contents(texts)
    new_texts = []
    seen = set(existing)

    for text in texts:
        normalized_text = normalize_content(text)
        if not normalized_text or normalized_text in seen:
            continue
        seen.add(normalized_text)
        new_texts.append(normalized_text)

    if not new_texts:
        return 0

    embeddings = embed_passages(new_texts)
    return vector_store.add(new_texts, embeddings, title=title, source=source)

