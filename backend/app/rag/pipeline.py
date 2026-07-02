import os
from llama_cpp import Llama
from app.core.embeddings import embed_query
from app.core.vector_store import vector_store
from pathlib import Path

current_file_path = Path(__file__).resolve()
BASE_DIR = current_file_path.parent.parent.parent
MODEL_PATH = os.path.join(BASE_DIR, "models", "qwen2.5-1.5b-instruct-q5_k_m.gguf")

# Inicializa o modelo otimizado para CPU
# n_ctx: tamanho da janela de contexto (importante para contratos longos)
# n_threads: ajuste para o número de núcleos físicos do seu processador
llm = Llama(
    model_path=MODEL_PATH,
    n_ctx=3072, 
    n_threads=3, 
    verbose=False
)

def generate_response(prompt: str | list) -> str:
    if isinstance(prompt, str):
        messages = [{"role": "user", "content": prompt}]
    else:
        messages = prompt

    output = llm.create_chat_completion(
        messages=messages,
        max_tokens=1024,
        temperature=0.1, # Baixa temperatura para análise jurídica (mais determinístico)
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
    full_prompt = f"""<|im_start|>system
        Você é um assistente jurídico especialista. Analise o contrato abaixo de forma objetiva.
        Regras:
        1. Responda APENAS com base no contexto.
        2. Identifique desequilíbrios, multas abusivas ou ilegalidades.
        3. Finalize com: Score de Risco: [VALOR]/1000 - [Justificativa]

        Contexto:
        {context}

        Pergunta: {question}

        Finalize com: Score de Risco: [VALOR]/1000 - [Justificativa]
        """
    
    # Gerando resposta com llama-cpp (muito mais rápido em CPU)
    response = llm(
        full_prompt,
        max_tokens=1024,
        stop=["<|im_end|>"],
        echo=False
    )

    return response["choices"][0]["text"].strip()