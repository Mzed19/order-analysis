import faiss
import json
import numpy as np
from app.core.embeddings import EMBEDDING_DIM
from infra.database.postgres import get_conn, release_conn


def parse_embedding(value):
    if isinstance(value, str):
        return json.loads(value)
    return value


def normalize_content(value):
    return " ".join(value.split())

class VectorStore:
    def __init__(self, dim: int):
        self.index = faiss.IndexFlatIP(dim)
        self.documents = []
        self.dim = dim

        self._load_from_db()

    def _load_from_db(self):
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT c.content, c.embedding, d.title, d.source
                    FROM chunks c
                    JOIN documents d ON d.id = c.document_id
                    ORDER BY c.id
                """)
                rows = cur.fetchall()

            if rows:
                compatible_rows = []
                skipped_count = 0

                for row in rows:
                    embedding = parse_embedding(row[1])
                    if len(embedding) != self.dim:
                        skipped_count += 1
                        continue
                    compatible_rows.append((row, embedding))

                if skipped_count:
                    print(f"Skipped {skipped_count} chunks with incompatible embedding dimensions.")

                if not compatible_rows:
                    return

                embeddings = np.array([embedding for _, embedding in compatible_rows], dtype="float32")
                metadata = [(row[0], row[2], row[3]) for row, _ in compatible_rows]

                faiss.normalize_L2(embeddings)

                self.index.add(embeddings)
                self.documents.extend(metadata)

        finally:
            release_conn(conn)

    def existing_contents(self, texts):
        normalized_texts = [normalize_content(text) for text in texts if text and text.strip()]
        if not normalized_texts:
            return set()

        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT content, embedding
                    FROM chunks
                    WHERE content = ANY(%s)
                    """,
                    (normalized_texts,)
                )
                return {
                    row[0]
                    for row in cur.fetchall()
                    if len(parse_embedding(row[1])) == self.dim
                }
        finally:
            release_conn(conn)

    def add(self, texts, embeddings, title=None, source=None):
        unique_texts = []
        unique_embeddings = []
        existing = self.existing_contents(texts)
        seen = set(existing)

        for text, emb in zip(texts, embeddings):
            normalized_text = normalize_content(text)
            if not normalized_text or normalized_text in seen:
                continue

            seen.add(normalized_text)
            unique_texts.append(normalized_text)
            unique_embeddings.append(emb)

        if not unique_texts:
            return 0

        texts = unique_texts
        embeddings = np.array(unique_embeddings, dtype="float32")
        embeddings = embeddings.astype("float32")
        if embeddings.ndim != 2 or embeddings.shape[1] != self.dim:
            raise ValueError(
                f"Embedding dimension mismatch: expected {self.dim}, got {embeddings.shape[1]}"
            )
        faiss.normalize_L2(embeddings)

        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO documents (title, source) VALUES (%s, %s) RETURNING id",
                    (title, source)
                )
                document_id = cur.fetchone()[0]

                for text, emb in zip(texts, embeddings):
                    cur.execute(
                        "INSERT INTO chunks (document_id, content, embedding) VALUES (%s, %s, %s)",
                        (document_id, text, emb.tolist())
                    )

            conn.commit()

        finally:
            release_conn(conn)

        self.index.add(embeddings)
        self.documents.extend([(t, title, source) for t in texts])
        return len(texts)

    def search(self, query_embedding, k=10):
        if self.index.ntotal == 0:
            return []

        query_embedding = np.array(query_embedding).astype("float32")
        if query_embedding.ndim != 2 or query_embedding.shape[1] != self.dim:
            raise ValueError(
                f"Query embedding dimension mismatch: expected {self.dim}, got {query_embedding.shape[1]}"
            )
        faiss.normalize_L2(query_embedding)

        scores, indices = self.index.search(query_embedding, min(k * 3, self.index.ntotal))

        results = []
        seen = set()

        for idx, i in enumerate(indices[0]):
            if i == -1:
                continue

            content, title, source = self.documents[int(i)]
            result_key = (content, title, source)
            if result_key in seen:
                continue

            seen.add(result_key)
            results.append({
                "content": self.documents[int(i)][0],
                "title": self.documents[int(i)][1],
                "source": self.documents[int(i)][2],
                "score": float(scores[0][idx])
            })

            if len(results) >= k:
                break

        return results


vector_store = VectorStore(dim=EMBEDDING_DIM)

