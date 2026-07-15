import os
from llama_cpp import Llama
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
        temperature=0.0, # Baixa temperatura para análise jurídica (mais determinístico)
        repeat_penalty=1.1
    )
    return output["choices"][0]["message"]["content"]

def ask(question: str):
    from app.core.embeddings import embed_query
    from app.core.vector_store import vector_store

    query_embedding = embed_query([question])
    results = vector_store.search(query_embedding, k=5)
    
    context = "\n\n".join(
        f"Fonte: {result.get('title') or result.get('source') or 'documento'}\n{result['content']}"
        for result in results
    )

    if not context:
        return "Não encontrei contexto suficiente na base vetorial."

    system_message = {
        "role": "system",
        "content": (
            "Você é um analista de crédito especializado em avaliar pedidos de compra. "
            "Responda à pergunta do usuário baseando-se EXCLUSIVAMENTE nas informações de contexto fornecidas abaixo. "
            "Se as informações de contexto não forem suficientes para responder, diga claramente que não possui essa informação."
        ),
    }

    user_message = {
        "role": "user",
        "content": f"Contexto:\n{context}\n\nPergunta: {question}",
    }

    return generate_response([system_message, user_message])