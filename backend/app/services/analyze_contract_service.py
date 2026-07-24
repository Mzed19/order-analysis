from app.core.redis_cache import make_contract_cache_key, get_contract_chunks, set_contract_chunks
from app.core.embeddings import embed_passages, embed_query
import numpy as np
import re
from typing import Any
from app.rag.pipeline import generate_response

# Queries distintas para não perder indicadores críticos em dossiês longos.
RETRIEVAL_QUERIES = [
    "quantidade de protestos títulos protestados restrições",
    "processos judiciais polo passivo recuperação judicial falência",
    "score Serasa Sivee limite de crédito aprovação",
    "créditos vencidos créditos baixados prejuízo atraso pagamento",
    "valor do pedido compra parcelas CNPJ razão social",
]

ANALYSIS_QUERY = " ".join(RETRIEVAL_QUERIES)

SYSTEM_MESSAGE = {
    "role": "system",
    "content": (
        "Você é um Analista de Crédito Sênior. "
        "Você só afirma o que está explícito no dossiê. "
        "Você nunca inventa indicadores, nunca interpreta data de compra como inadimplência "
        "e nunca se contradiz na mesma resposta. "
        "Se um dado não aparece no dossiê, diga 'não informado' — não complete com suposição."
    ),
}

CREDIT_RULES = """
## Definições (obrigatórias)
- INADIMPLÊNCIA: só existe se o dossiê citar atraso, créditos vencidos, títulos em aberto, baixas a prejuízo, cobrança ou restrição por falta de pagamento. Data da última compra NÃO é inadimplência.
- ÚLTIMA COMPRA / tempo sem comprar: indicador comercial de relacionamento. NÃO use como fator de risco, restrição ou inadimplência. Ignore completamente na decisão.
- PROTESTOS: só afirme se houver quantidade > 0 ou menção explícita de protesto ativo. Se o campo estiver zerado, em branco, "não consta", "nada consta" ou ausente → protestos = não informado / inexistentes. Nunca diga "há histórico de protestos" e depois "não há informação sobre protestos".
- PROCESSOS JUDICIAIS: só considere polo passivo relevante (réu). Menção genérica sem quantidade/polo não é veto automático.
- LIMITE DE CRÉDITO e SCORE: use apenas se constarem no dossiê, com o valor citado.

## Regras de coerência
1. Extraia fatos antes de opinar. A justificativa só pode usar fatos que você listou.
2. Não invente números, percentuais de indicadores ou históricos.
3. Não use linguagem absoluta ("impede a aprovação", "histórico grave") sem dado quantitativo explícito.
4. Se faltar indicador crítico (ex.: protestos/score não informados), prefira ANÁLISE MANUAL em vez de NEGAR por presunção.
5. Seja direto, coeso e sem frases que se anulem.
""".strip()

CHUNK_SIZE = 700
OVERLAP = 100
MAX_CHUNKS = 8

# Orçamento de tokens para o contexto do contrato.
# Janela total = 4096. Reserva ~1000 tokens para system + template
# e ~600 tokens para a resposta. Restam ~2500 tokens para o dossiê.
_MAX_CONTEXT_CHARS = 2500 * 3  # ~7500 caracteres


def _estimate_fits_context(text: str) -> bool:
    """Verifica se o texto cabe no orçamento de tokens do contexto."""
    return len(text) <= _MAX_CONTEXT_CHARS


def analyze_contract(contract_text: str, filename: str | None = None, progress_callback=None) -> list[str]:
    print(f"Analisando pedido de compra: filename={filename}, texto[:200]={contract_text[:200]}...")
    if not contract_text.strip():
        raise ValueError("O texto do documento está vazio.")

    if progress_callback:
        progress_callback(chunks_quantity=2, analyzed_chunks_quantity=0)

    if _estimate_fits_context(contract_text):
        print("Analisando dados do pedido de compra (texto completo)...")
        context = contract_text
    else:
        print("Texto excede a janela de contexto. Selecionando trechos relevantes...")
        chunks = build_chunks(contract_text)
        relevant_texts = select_relevant_chunks(chunks)
        context = "\n\n".join(relevant_texts)

    # Passo 1: extrair só fatos (reduz alucinação em modelos pequenos)
    print("Passo 1/2: extraindo fatos do dossiê...")
    facts = generate_response(
        [SYSTEM_MESSAGE, {"role": "user", "content": build_facts_prompt(context)}],
        max_tokens=500,
    )

    if progress_callback:
        progress_callback(analyzed_chunks_quantity=1)

    # Passo 2: parecer baseado nos fatos extraídos
    print("Passo 2/2: emitindo parecer...")
    analysis = generate_response(
        [SYSTEM_MESSAGE, {"role": "user", "content": build_analysis_prompt_for_context(context, facts)}],
        max_tokens=700,
    )

    if progress_callback:
        progress_callback(analyzed_chunks_quantity=2)

    return [analysis]


def get_or_create_chunks(contract_text: str, filename: str | None = None) -> list[dict[str, Any]]:
    cache_key = make_contract_cache_key(contract_text, filename)
    chunks = get_contract_chunks(cache_key)
    if chunks:
        return chunks

    chunks = build_chunks(contract_text)
    set_contract_chunks(cache_key, chunks)
    return chunks


def build_facts_prompt(context: str) -> str:
    return f"""
Leia o dossiê e extraia APENAS fatos explícitos. Não interprete, não recomende, não calcule risco.

Para cada item, use o valor literal do dossiê ou "não informado":
- Razão social / CNPJ:
- Valor do pedido / parcelas:
- Score (nome e valor):
- Limite de crédito:
- Protestos (quantidade; se 0 ou ausente, escreva "não informado ou zero"):
- Processos judiciais no polo passivo (quantidade/detalhe):
- Créditos vencidos / prejuízo / atraso:
- Recuperação judicial / falência:
- Outros indicadores de risco explícitos:
- Última compra (apenas registre a data; NÃO classifique como risco):

Proibido: concluir inadimplência a partir da data da última compra; afirmar protestos sem quantidade > 0.

==================================================
DOSSIÊ:
{context}
""".strip()


def build_analysis_prompt_for_context(context: str, facts: str | None = None) -> str:
    facts_block = ""
    if facts:
        facts_block = f"""
## Fatos já extraídos (use como fonte principal; o dossiê só confirma)
{facts.strip()}
"""

    return f"""
Você é um Analista de Crédito Sênior. Emita um parecer decisivo sobre o pedido de compra.

{CREDIT_RULES}
{facts_block}
## Exemplos do que NÃO fazer
- Errado: "última compra em 2025-03-24 indica inadimplência".
- Certo: ignorar a data da última compra na decisão.
- Errado: "há histórico de protestos" e na mesma frase "não há informação sobre protestos".
- Certo: se não há quantidade > 0, diga que protestos não estão evidenciados e, se necessário, peça ANÁLISE MANUAL.

## Formato de Saída (obrigatório — só estes campos)
**RECOMENDAÇÃO:** [APROVAR, NEGAR ou ANÁLISE MANUAL]

**PORCENTAGEM DE RISCO:** [0% a 100%, coerente com os fatos; se dados críticos faltarem, não use risco extremo sem evidência]

**JUSTIFICATIVA CRÍTICA:** [Até 5 linhas, coesas, sem contradição. Cite valores explícitos. Não mencione última compra como risco.]

**CONTRA-PROPOSTA:** [Se NEGAR: alternativa concreta (reduzir valor, garantir pagamento antecipado, etc.). Se APROVAR ou ANÁLISE MANUAL: "Não se aplica."]

==================================================
DOSSIÊ DO CLIENTE:
{context}
""".strip()


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
    """Recupera trechos por várias queries e funde os melhores (sem duplicar)."""
    matrix = np.array([chunk["embedding"] for chunk in chunks], dtype="float32")
    best_scores: dict[int, float] = {}

    for query in RETRIEVAL_QUERIES:
        query_embedding = embed_query([query])[0]
        scores = cosine_similarity(query_embedding, matrix)
        # top-3 por query
        top = list(np.argsort(scores)[-3:][::-1])
        for idx in top:
            score = float(scores[idx])
            if score <= 0:
                continue
            if idx not in best_scores or score > best_scores[idx]:
                best_scores[idx] = score

    ranked = sorted(best_scores.items(), key=lambda item: item[1], reverse=True)
    selected: list[str] = []
    total_chars = 0
    for idx, _ in ranked:
        text = chunks[idx]["text"]
        if text in selected:
            continue
        if total_chars + len(text) > _MAX_CONTEXT_CHARS and selected:
            break
        selected.append(text)
        total_chars += len(text)
        if len(selected) >= MAX_CHUNKS:
            break

    return selected or [chunks[0]["text"]]


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
