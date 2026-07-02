from app.core.redis_cache import make_contract_cache_key, get_contract_chunks, set_contract_chunks
from app.core.embeddings import embed_passages, embed_query
import numpy as np
import re
from typing import Any
from app.rag.pipeline import generate_response

ANALYSIS_QUERY = (
    "Cláusulas abusivas, multas excessivas, rescisão unilateral, responsabilidade civil, "
    "prazos leoninos, riscos financeiros e pegadinhas contratuais no texto."
)

SYSTEM_MESSAGE = {
    "role": "system",
    "content": (
        "Você é um Analista de Risco Jurídico Sênior. Sua comunicação é executiva, direta e focada em resultados. "
        "Sua missão é extrair insights imediatos de contratos, apontando riscos reais sem rodeios. "
        "Evite textos longos, explicações genéricas ou redundâncias. Vá direto ao ponto."
    ),
}

CHUNK_SIZE = 700
OVERLAP = 100
MAX_CHUNKS = 6

def analyze_contract(contract_text: str, filename: str | None = None, progress_callback=None) -> list[str]:
    print(f"Analisando contrato: filename={filename}, texto[:200]={contract_text[:200]}...")
    chunks = get_or_create_chunks(contract_text, filename)
    relevant_chunks = select_relevant_chunks(chunks)
    print(f"Chunks relevantes encontrados: {len(relevant_chunks)}")
    if not relevant_chunks:
        raise ValueError("Não foram encontrados trechos relevantes para análise.")

    if progress_callback:
        progress_callback(chunks_quantity=len(relevant_chunks), analyzed_chunks_quantity=0)

    analyses = []
    for i, chunk in enumerate(relevant_chunks):
        print(f"Analisando chunk {i+1}/{len(relevant_chunks)}: {chunk[:100]}...")
        prompt = build_analysis_prompt_for_chunk(chunk)
        messages = [SYSTEM_MESSAGE, {"role": "user", "content": prompt}]
        analysis = generate_response(messages)
        analyses.append(analysis)
        
        if progress_callback:
            progress_callback(analyzed_chunks_quantity=i + 1)

    print(f"Análises geradas: {len(analyses)}")
    return analyses

def get_or_create_chunks(contract_text: str, filename: str | None = None) -> list[dict[str, Any]]:
    cache_key = make_contract_cache_key(contract_text, filename)
    chunks = get_contract_chunks(cache_key)
    if chunks:
        return chunks

    chunks = build_chunks(contract_text)
    set_contract_chunks(cache_key, chunks)
    return chunks

def build_analysis_prompt_for_chunk(chunk: str) -> str:
    return (
        f"""Analise o trecho do contrato abaixo e entregue insights imediatos e estruturados.

DIRETRIZES:
1. Identifique apenas riscos REAIS e CONCRETOS.
2. Seja extremamente direto. Use frases curtas e impactantes.
3. Foque no impacto financeiro ou jurídico para a tomada de decisão.

FORMATO DA RESPOSTA:

### [Título do Risco]
- **Nível:** (Crítico/Médio/Baixo)
- **Impacto:** [Uma frase sobre o prejuízo potencial]
- **Insight:** [Explicação direta do problema]
- **Recomendação:** [Ação imediata: Alterar/Remover/Aceitar]

Se não houver riscos, não responda nada

TRECHO DO CONTRATO:
---
{chunk}
---
"""
    )

def build_chunks(contract_text: str) -> list[dict[str, Any]]:
    normalized = normalize_text(contract_text)
    chunks = chunk_text(normalized, chunk_size=CHUNK_SIZE, overlap=OVERLAP)
    if not chunks:
        raise ValueError("Não foi possível extrair trechos do contrato fornecido.")

    embeddings = embed_passages(chunks)
    return [
        {
            "text": chunk,
            "embedding": emb.tolist(),
        }
        for chunk, emb in zip(chunks, embeddings)
    ]

def select_relevant_chunks(chunks: list[dict[str, Any]]) -> list[str]:
    query_embedding = embed_query([ANALYSIS_QUERY])[0]
    matrix = np.array([chunk["embedding"] for chunk in chunks], dtype="float32")
    scores = cosine_similarity(query_embedding, matrix)
    top_indices = list(np.argsort(scores)[-MAX_CHUNKS:][::-1])
    return [chunks[i]["text"] for i in top_indices if scores[i] > 0]

def normalize_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())

def cosine_similarity(query: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    query_norm = np.linalg.norm(query)
    matrix_norm = np.linalg.norm(matrix, axis=1)
    if query_norm == 0 or np.any(matrix_norm == 0):
        return np.zeros(matrix.shape[0], dtype=float)
    return (matrix @ query) / (query_norm * matrix_norm)

def chunk_text(text: str, chunk_size: int = 1200, overlap: int = 150) -> list[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be greater than or equal to zero and smaller than chunk_size")

    normalized = normalize_text(text)
    if not normalized:
        return []

    chunks: list[str] = []
    start = 0

    while start < len(normalized):
        end = start + chunk_size
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(normalized):
            break
        start = end - overlap

    return chunks
