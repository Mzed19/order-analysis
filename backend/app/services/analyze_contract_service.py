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
        f"""Analise as informações do pedido de compra e os dados cadastrais/financeiros abaixo para realizar uma avaliação de risco de crédito.

DIRETRIZES DE ANÁLISE:
1. Compare o "Valor da Compra" com o "Limite de Crédito". Se o valor da compra for consideravelmente maior que o limite, isso representa um risco relevante de crédito.
2. Avalie o "Total de polos passivos em reais (Processos judiciais)". Valores elevados de processos judiciais em relação ao valor da compra indicam alta exposição jurídica e risco de bloqueios.
3. Avalie a "Quantidade Total (Protesto)". Qualquer valor acima de 0 indica restrições cadastrais ativas.
4. Verifique a existência de "Créditos Vencidos" ou "Créditos Baixados Como Prejuízo". Valores maiores que zero indicam histórico de inadimplência recente.
5. Avalie o "Score" do cliente (ex: Sivee PJ). Scores baixos (geralmente abaixo de 400) representam alto risco; intermediários (400-700) risco médio; altos (acima de 700) baixo risco.
6. Defina uma recomendação clara sobre aprovar ou não o pedido de compra.

FORMATO DA RESPOSTA (Siga rigorosamente esta estrutura):

### Decisão: [Aprovar / Não Aprovar / Revisão Manual]
- **Motivo:** [Explique resumidamente o motivo da decisão baseado nos cruzamentos de dados acima]
- **Fator Positivo:** [Ponto positivo identificado, ex: Score alto, ausência de protestos, etc.]
- **Fator Positivo:** [Outro ponto positivo (se houver)]
- **Fator Negativo:** [Ponto negativo/risco, ex: Compra excede o limite, processos judiciais elevados, etc.]
- **Fator Negativo:** [Outro ponto negativo (se houver)]
- **Ponto de Atenção:** [Recomendação de monitoramento ou mitigação de risco, ex: Exigir garantias, faturar parte à vista]
- **Ponto de Atenção:** [Outro ponto de atenção (se houver)]

Se o trecho não contiver nenhuma informação relevante sobre condições comerciais, cadastro ou pedido de compra, não responda nada.

TRECHO DO PEDIDO DE COMPRA:
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
