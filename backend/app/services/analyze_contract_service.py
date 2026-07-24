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

# Orçamento de tokens para o contexto do contrato.
# Janela total = 4096. Reserva ~800 tokens para system message + prompt template
# e ~500 tokens para a resposta gerada. Restam ~2800 tokens para o dossiê.
# Estimativa conservadora: ~3 chars por token em português.
_MAX_CONTEXT_CHARS = 2800 * 3  # ~8400 caracteres

def _estimate_fits_context(text: str) -> bool:
    """Verifica se o texto cabe no orçamento de tokens do contexto."""
    return len(text) <= _MAX_CONTEXT_CHARS

def analyze_contract(contract_text: str, filename: str | None = None, progress_callback=None) -> list[str]:
    print(f"Analisando pedido de compra: filename={filename}, texto[:200]={contract_text[:200]}...")
    if not contract_text.strip():
        raise ValueError("O texto do documento está vazio.")

    if progress_callback:
        progress_callback(chunks_quantity=1, analyzed_chunks_quantity=0)

    if _estimate_fits_context(contract_text):
        # Texto cabe inteiro na janela de contexto — usa diretamente
        print("Analisando dados do pedido de compra (texto completo)...")
        context = contract_text
    else:
        # Texto excede a janela — seleciona os trechos mais relevantes via embeddings
        print("Texto excede a janela de contexto. Selecionando trechos relevantes...")
        chunks = build_chunks(contract_text)
        relevant_texts = select_relevant_chunks(chunks)
        context = "\n\n".join(relevant_texts)

    prompt = build_analysis_prompt_for_context(context)
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
   return f"""
Você é um Analista de Crédito Sênior. Sua tarefa é analisar o dossiê financeiro e comercial de uma empresa e emitir um parecer decisivo sobre a viabilidade de um pedido de compra.

## Política de Risco
- Seu objetivo principal é proteger o caixa da empresa contra inadimplência.
- Fatores restritivos graves (como volume expressivo de protestos, recuperação judicial, ou processos judiciais relevantes no polo passivo) são critérios de veto imediato, independentemente do limite de crédito.
- O limite de crédito é apenas um facilitador, mas nunca anula o risco de indicadores negativos.
- O limite de crédito só deve ser mencionado se ele estiver no dossiê e for relevante para a análise.
- O valor da compra é o valor que o cliente está pedindo emprestado.
- Baseie seu racional estritamente no dossiê fornecido. Não faça presunções ou estimativas.
- A última compra do cliente não deve ser considerada.
## Formato de Saída (Obrigatório)
Retorne única e exclusivamente os 3 campos abaixo, sem saudações, introduções ou explicações adicionais.

**RECOMENDAÇÃO:** [APROVAR, NEGAR ou ANÁLISE MANUAL]

**PORCENTAGEM DE RISCO:** [Escreva a porcentagem de risco de inadimplência, de 0% a 100%, com base nos indicadores do dossiê.]

**JUSTIFICATIVA CRÍTICA:** [Escreva em até 5 linhas o racional financeiro da sua decisão. Destaque os valores absolutos e os indicadores de maior peso que fundamentaram o seu parecer.]

**CONTRA-PROPOSTA:** [Se a recomendação for NEGAR, sugira uma alternativa de negociação ou ajuste do pedido de compra que poderia reduzir o risco e viabilizar a aprovação.]
==================================================
DOSSIÊ DO CLIENTE:
{context}
"""
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
