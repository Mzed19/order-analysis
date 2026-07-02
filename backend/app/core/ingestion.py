from app.core.vector_store import vector_store
from app.core.embeddings import embed_passages

def embedAndStore(texts):
    embeddings = embed_passages(texts)
    vector_store.add(texts, embeddings)

