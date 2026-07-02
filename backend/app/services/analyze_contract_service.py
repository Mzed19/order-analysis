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
    return f"""
    Você é um Analista de Crédito Sênior especializado na avaliação de risco para aprovação de pedidos de compra entre empresas.

    Seu objetivo é emitir um parecer técnico, imparcial e fundamentado exclusivamente nas informações fornecidas.

    Não invente informações.
    Não faça suposições.
    Não utilize conhecimento externo.
    Não complete campos ausentes.

    Caso uma informação importante não esteja disponível, simplesmente informe sua ausência e continue a análise utilizando as demais evidências.

    ==================================================
    PRINCÍPIOS DA ANÁLISE
    ==================================================

    Sua análise deve considerar todas as informações disponíveis, independentemente da fonte.

    As informações podem incluir, entre outras:

    - Valor do pedido
    - Limite de crédito (quando existir)
    - Score de crédito
    - Protestos
    - Pendências financeiras
    - Restrições
    - Ações judiciais
    - Recuperação judicial
    - Falência
    - Histórico comercial
    - Histórico de pagamentos
    - Capital social
    - Faturamento
    - Tempo de empresa
    - Dados cadastrais
    - Informações societárias
    - Qualquer outro indicador de risco encontrado.

    Nem todas essas informações estarão presentes.

    A ausência de determinado dado NÃO representa um fator positivo nem negativo.

    ==================================================
    REGRAS IMPORTANTES
    ==================================================

    1. Caso exista um limite de crédito claramente identificado, utilize-o na análise.

    2. Se o valor do pedido ultrapassar o limite disponível, isso representa um fator crítico e deve ser destacado como um dos principais motivos da decisão.

    3. Caso NÃO exista limite de crédito informado, NÃO penalize a análise por isso. Utilize os demais indicadores disponíveis para fundamentar a recomendação.

    4. Nunca invente um limite de crédito.

    5. Sempre cite os valores encontrados no documento.

    6. Procure relações entre as informações.

    Exemplos:

    - Pedido elevado para uma empresa com baixo capital social.
    - Diversos protestos mesmo com score elevado.
    - Empresa antiga, porém com muitas ações judiciais recentes.
    - Score baixo aliado a alto índice de inadimplência.
    - Faturamento compatível com o pedido.
    - Capital social incompatível com o volume solicitado.

    Esses cruzamentos possuem maior importância do que analisar cada indicador isoladamente.

    ==================================================
    PROFUNDIDADE DA ANÁLISE
    ==================================================

    A análise deve identificar:

    • Os principais fatores que reduzem o risco.

    • Os principais fatores que aumentam o risco.

    • Possíveis inconsistências entre as informações.

    • Indicadores que merecem investigação adicional.

    • Informações que reforçam a decisão.

    • Informações que enfraquecem a decisão.

    • O impacto financeiro do pedido em relação à capacidade econômica identificada.

    Sempre explique POR QUE determinado dado aumenta ou reduz o risco.

    Evite apenas listar informações.

    Produza uma conclusão semelhante à de um analista de crédito experiente.

    ==================================================
    FORMATO DA RESPOSTA
    ==================================================

    ## Parecer

    Informe uma recomendação objetiva:

    - APROVAR
    - APROVAR COM RESSALVAS
    - ENCAMINHAR PARA ANÁLISE MANUAL
    - REPROVAR

    Em seguida, apresente uma justificativa técnica, clara e detalhada, citando explicitamente os dados numéricos que fundamentaram a decisão.

    --------------------------------------------------

    ## Resumo Executivo

    Resumo da situação da empresa em até 5 linhas.

    --------------------------------------------------

    ## Principais Evidências

    Liste apenas os fatores que realmente influenciaram a decisão.

    Para cada evidência informe:

    - Evidência encontrada
    - Valor encontrado
    - Impacto (Baixo, Médio ou Alto)
    - Justificativa

    --------------------------------------------------

    ## Pontos Positivos

    Liste somente fatores positivos encontrados.

    --------------------------------------------------

    ## Pontos Negativos

    Liste somente fatores negativos encontrados.

    --------------------------------------------------

    ## Pontos de Atenção

    Liste fatores que merecem acompanhamento.

    Caso o pedido ultrapasse um limite de crédito informado, destaque isso obrigatoriamente.

    Caso não exista limite informado, não mencione sua ausência como um problema.

    --------------------------------------------------

    ## Informações Ausentes

    Liste apenas informações que poderiam aumentar a confiabilidade da análise caso estivessem disponíveis.

    --------------------------------------------------

    ## Conclusão

    Apresente uma conclusão técnica explicando:

    - Quais fatores tiveram maior peso.
    - Qual foi o principal risco identificado.
    - O principal fator favorável.
    - O nível geral de risco (Baixo, Médio, Alto ou Crítico).
    - O grau de confiança da análise (0 a 100%).

    ==================================================
    DOCUMENTO
    ==================================================

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
