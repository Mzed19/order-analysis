import os
from llama_cpp import Llama
from app.core.embeddings import embed_query
from app.core.vector_store import vector_store
from pathlib import Path

current_file_path = Path(__file__).resolve()
BASE_DIR = current_file_path.parent.parent.parent
MODEL_PATH = os.path.join(BASE_DIR, "models", os.getenv("GENERATION_MODEL_NAME", "Qwen2.5-3B-Instruct-Q5_K_M.gguf"))

# Inicializa o modelo otimizado para CPU
# n_ctx: tamanho da janela de contexto (importante para contratos longos)
# n_threads: ajuste para o número de núcleos físicos do seu processador
llm = Llama(
    model_path=MODEL_PATH,
    n_ctx=4096, 
    n_threads=3, 
    verbose=False
)

print(f"Modelo de geração carregado: {MODEL_PATH}")

def generate_response(prompt: str | list) -> str:
    if isinstance(prompt, str):
        messages = [{"role": "user", "content": prompt}]
    else:
        messages = prompt

    output = llm.create_chat_completion(
        messages=messages,
        max_tokens=1024,
        temperature=0.0, # Baixa temperatura para análise jurídica (mais determinístico)
        repeat_penalty=1.1
    )
    return output["choices"][0]["message"]["content"]

def ask(question: str):
    query_embedding = embed_query([question])
    results = vector_store.search(query_embedding, k=5)
    
    context = "\n\n".join(
        f"Fonte: {result.get('title') or result.get('source') or 'documento'}\n{result['content']}"
        for result in results
    )

    if not context:
        return "Não encontrei contexto suficiente na base vetorial."

    # Prompt System + User (Melhorado para modelos menores)
    full_prompt = f"""
        Você é um analista de crédito especializado em avaliar pedidos de compra.

        Você receberá:
        - O CPF ou CNPJ do solicitante (apenas um identificador, não é um dado financeiro).
        - Os dados financeiros do pedido de compra, incluindo obrigatoriamente o valor do pedido.
        - Um contexto recuperado pelo sistema RAG contendo conhecimentos relevantes para análise de crédito.

        Sua tarefa é:
        1. Comparar o valor do pedido com as demais informações financeiras do contexto.
        2. Avaliar o risco de concessão de crédito considerando exclusivamente os dados fornecidos.
        3. Não criar, assumir ou inferir informações que não estejam presentes no contexto ou no pedido.

        Retorne uma resposta curta no seguinte formato:

        Decisão: APROVAR ou NEGAR

        Motivos:
        - Motivo 1
        - Motivo 2
        - Motivo 3

        Regras:
        - Seja objetivo e técnico.
        - Utilize apenas as informações fornecidas.
        - Se os dados forem insuficientes para uma conclusão segura, retorne "NEGAR" e informe que não há informações suficientes para aprovação.
        - Nunca utilize o CPF ou CNPJ como critério de análise; ele serve apenas para identificar o titular.
    """
    
    # Gerando resposta com llama-cpp (muito mais rápido em CPU)
    response = llm(
        full_prompt,
        max_tokens=1024,
        stop=["<|im_end|>"],
        echo=False
    )

    return response["choices"][0]["text"].strip()