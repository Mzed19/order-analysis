from app.core.redis_cache import make_contract_cache_key, get_contract_chunks, set_contract_chunks
from app.core.embeddings import embed_passages, embed_query
import numpy as np
import re
from typing import Any
from app.rag.pipeline import generate_response

ANALYSIS_QUERY = (
    "Valor da compra, parcelas, CNPJ, nome fantasia, quantidade de protestos, "
    "processos judiciais (polos passivos), limite de crédito, créditos vencidos, "
    "créditos baixados como prejuízo, score Sivee pj, condições de aprovação."
)

SYSTEM_MESSAGE = {
    "role": "system",
    "content": (
        "Você é um Analista de Crédito Sênior especializado na avaliação de pedidos de compra e relatórios de risco financeiro. "
        "Sua missão é analisar os indicadores de crédito (como score, limite de crédito, processos judiciais, protestos e inadimplência) "
        "para determinar se a concessão de crédito para o pedido de compra deve ser aprovada ou não. "
        "Sua comunicação é extremamente direta, executiva e focada em resultados. Vá direto ao ponto."
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
        progress_callback(chunks_quantity=1, analyzed_chunks_quantity=0)

    # Consolidar todos os trechos relevantes em um único contexto para evitar redundância
    combined_context = "\n\n".join(relevant_chunks)

    print("Analisando contexto consolidado do pedido de compra...")
    prompt = build_analysis_prompt_for_context(combined_context)
    messages = [SYSTEM_MESSAGE, {"role": "user", "content": prompt}]
    analysis = generate_response(messages)

    if progress_callback:
        progress_callback(analyzed_chunks_quantity=1)

    return [analysis]

def get_or_create_chunks(contract_text: str, filename: str | None = None) -> list[dict[str, Any]]:
    cache_key = make_contract_cache_key(contract_text, filename)
    chunks = get_contract_chunks(cache_key)
    if chunks:
        return chunks

    chunks = build_chunks(contract_text)
    set_contract_chunks(cache_key, chunks)
    return chunks

def build_analysis_prompt_for_context(context: str) -> str:
    return (
        f"""Analise as informações do pedido de compra e os dados cadastrais/financeiros abaixo para realizar uma avaliação de risco de crédito consolidada e extremamente precisa.

DIRETRIZES DE ANÁLISE:
1. Baseie sua decisão em dados concretos do texto (valores, limites, ações judiciais, protestos e score).
2. Mencione explicitamente os valores numéricos e dados específicos (valores em reais, quantidade de protestos, pontuação de score) que determinaram a sua decisão de crédito.
3. Compare o valor total do pedido com o limite de crédito disponível e aponte a discrepância de valores.
4. Pondere o risco do valor dos processos judiciais ativos (polos passivos) e a presença de protestos.
5. Evite redundâncias. Entregue uma única resposta conclusiva e direta.

FORMATO DA RESPOSTA (Siga rigorosamente esta estrutura):

### Decisão: [Aprovar / Não Aprovar / Revisão Manual]
- **Motivo:** [Justificativa clara citando explicitamente os dados numéricos determinantes do texto, ex: 'O valor da compra de R$ X excede o limite de crédito de R$ Y em Z vezes.']
- **Fator Positivo:** [Ponto positivo identificado com seu respectivo valor/métrica, ex: 'Score Sivee de X é considerado bom', 'Zero protestos ativos', etc.]
- **Fator Positivo:** [Outro ponto positivo se houver]
- **Fator Negativo:** [Risco identificado com seu respectivo valor/métrica, ex: 'Processos judiciais como polo passivo totalizam R$ X', etc.]
- **Fator Negativo:** [Outro ponto negativo se houver]
- **Ponto de Atenção:** [Recomendação prática de mitigação de risco com base nos dados, ex: 'Faturar apenas até o limite de R$ X e exigir sinal de Y%']
- **Ponto de Atenção:** [Outro ponto de atenção se houver]

DADOS DO DOCUMENTO:
---
{context}
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
