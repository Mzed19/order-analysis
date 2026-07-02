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
    print(f"Analisando pedido de compra: filename={filename}, texto[:200]={contract_text[:200]}...")
    if not contract_text.strip():
        raise ValueError("O texto do documento está vazio.")

    if progress_callback:
        progress_callback(chunks_quantity=1, analyzed_chunks_quantity=0)

    # Analisa diretamente o texto completo do pedido para evitar fatiamento redundante
    # e contaminações de diretrizes jurídicas da antiga base de dados do RAG.
    print("Analisando dados do pedido de compra...")
    prompt = build_analysis_prompt_for_context(contract_text)
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

def extract_numeric_value(text: str, patterns: list[str]) -> float | None:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            val_str = match.group(1)
            val_str = re.sub(r"[^\d,\.]", "", val_str)
            # Formato brasileiro: 1.000.000,00 -> 1000000.00
            if "," in val_str and "." in val_str:
                val_str = val_str.replace(".", "").replace(",", ".")
            elif "," in val_str:
                val_str = val_str.replace(",", ".")
            elif "." in val_str:
                parts = val_str.split(".")
                if len(parts[-1]) == 3:
                    val_str = val_str.replace(".", "")
            try:
                return float(val_str)
            except ValueError:
                continue
    return None

def format_currency_br(val: float) -> str:
    return f"{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def check_credit_limit(text: str) -> str:
    valor_compra = extract_numeric_value(text, [
        r"Valor da Compra\s*R\$\s*([\d\.,]+)",
        r"Valor\s*R\$\s*([\d\.,]+)",
        r"Valor da Compra\s*([\d\.,]+)",
        r"Valor\s*([\d\.,]+)",
    ])
    limite_credito = extract_numeric_value(text, [
        r"Limite de Crédito\s*(?:\([^\)]+\))?\s*R\$\s*([\d\.,]+)",
        r"Limite\s*(?:\([^\)]+\))?\s*R\$\s*([\d\.,]+)",
        r"Limite de Crédito\s*([\d\.,]+)",
        r"Limite\s*([\d\.,]+)",
    ])

    if valor_compra is not None and limite_credito is not None:
        if valor_compra > limite_credito:
            excedente = valor_compra - limite_credito
            return (
                f"\n[FATO MATEMÁTICO REAL]: O valor do pedido (R$ {format_currency_br(valor_compra)}) EXCEDEU o limite de crédito "
                f"(R$ {format_currency_br(limite_credito)}) em R$ {format_currency_br(excedente)}. O limite de crédito é INSUFICIENTE. "
                f"A recomendação deve ser NEGAR ou colocar em ANÁLISE MANUAL.\n"
            )
        else:
            disponivel = limite_credito - valor_compra
            return (
                f"\n[FATO MATEMÁTICO REAL]: O valor do pedido (R$ {format_currency_br(valor_compra)}) é MENOR OU IGUAL ao limite de crédito "
                f"(R$ {format_currency_br(limite_credito)}). Há saldo disponível de R$ {format_currency_br(disponivel)}. "
                f"O limite de crédito é SUFICIENTE. Você NÃO deve dizer que o limite é insuficiente, pois R$ {format_currency_br(valor_compra)} "
                f"cabe perfeitamente dentro de R$ {format_currency_br(limite_credito)}.\n"
            )
    return ""

def build_analysis_prompt_for_context(context: str) -> str:
    fato_matematico = check_credit_limit(context)
    return f"""
   Você é um sistema especialista em Análise de Crédito Sênior. Seu objetivo é emitir uma recomendação estritamente técnica, direta e sem rodeios sobre a aprovação ou negativa de um pedido de compra entre empresas. 

Você não deve resumir o contexto, mas sim tomar uma decisão baseada em fatos de risco.

## Diretrizes de Decisão (Rigidez Lógica)
- **Prioridade de Veto:** Fatores de risco crítico (protestos ativos, recuperação judicial, score abaixo da política, pedido acima do limite) anulam automaticamente dados históricos positivos (como tempo de empresa ou capital social). 
- **Regra Anti-Contradição:** Se houver um fator de risco crítico, a recomendação deve ser NEGAR ou ANÁLISE MANUAL. Nunca atenue um risco real justificando que a empresa "é antiga" ou "tem bom faturamento".
- **Uso do Contexto:** Baseie-se exclusivamente nos dados fornecidos. Não presuma, não invente e não estime dados ausentes.
- **Ausência de Limite:** Se não houver limite de crédito informado, ignore esta variável e decida com base nos outros indicadores (protestos, score, faturamento). Nunca trate a ausência de limite como um ponto negativo.

## Critérios de Avaliação
- **Divergência de Dados:** Se o RAG trouxer informações conflitantes sobre o mesmo indicador, adote a postura mais conservadora (maior risco) e cite o conflito.
- **Foco no Risco:** Ignore dados cadastrais irrelevantes (endereço, CNAE secundário). Foque apenas em saúde financeira e capacidade de pagamento.

## Formato da Resposta (Siga Estritamente)

**RECOMENDAÇÃO:** [APROVAR, NEGAR ou ANÁLISE MANUAL]

**JUSTIFICATIVA CRÍTICA:**
[Insira aqui a explicação direta em no máximo 3 frases. Vá direto aos fatos que determinaram a decisão, citando valores, quantidades e o impacto financeiro imediato.]

**EVIDÊNCIAS DETERMINANTES:**
- [Indicador 1]: [Valor encontrado] -> [Impacto exato no risco]
- [Indicador 2]: [Valor encontrado] -> [Impacto exato no risco]
- [Indicador 3]: [Valor encontrado] -> [Impacto exato no risco]

==================================================
DADOS PARA ANÁLISE (CONTEXTO DO RAG)
==================================================
{context}

{fato_matematico}
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
