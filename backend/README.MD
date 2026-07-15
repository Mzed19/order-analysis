# 📄 ContractAI Backend - Análise Inteligente de Documentos

Este é o motor de processamento do **ContractAI**, uma plataforma avançada para análise de documentos financeiros e contratos utilizando Inteligência Artificial (RAG - Retrieval-Augmented Generation).

---

## 🚀 Tecnologias Core

- **Python 3.10+**: Linguagem principal.
- **RAG Pipeline**: Implementação personalizada utilizando `llama-cpp-python` para inferência local de LLMs.
- **Vector Store**: FAISS para busca semântica de alta performance.
- **Queue System**: Redis para gerenciamento de tarefas e processamento assíncrono.
- **Auth**: Validação de tokens JWT integrada com Keycloak (RS256).
- **Database**: PostgreSQL para armazenamento de metadados e resultados das análises.

## 📋 Pré-requisitos

- **Docker & Docker Compose**: Recomendado para rodar a infraestrutura (Redis, Postgres).
- **Python 3.10+**: Caso deseje rodar os serviços nativamente.
- **Keycloak**: Instância configurada para autenticação.

## 🛠️ Configuração Inicial

### 1. Variáveis de Ambiente
Crie um arquivo `.env` na raiz da pasta `backend` (veja `.env.example` se disponível):
```env
POSTGRES_HOST=localhost
POSTGRES_DB=ragdb
REDIS_URL=redis://localhost:6379/0
KEYCLOAK_URL=https://sua-url-keycloak.com/auth
KEYCLOAK_REALM=Contract AI
```

### 2. Download do Modelo LLM
O projeto utiliza o modelo **Qwen 2.5 1.5B** em formato GGUF para rodar localmente. Baixe-o utilizando o comando abaixo:

```bash
pip install huggingface_hub
hf download Qwen/Qwen2.5-1.5B-Instruct-GGUF qwen2.5-1.5b-instruct-q5_k_m.gguf --local-dir ./models

hf download intfloat/multilingual-e5-base --local-dir ./models/multilingual-e5-base
```


## 🐳 Executando com Docker

A maneira mais prática de rodar o projeto completo:

```bash
# Subir o banco de dados e serviços básicos
docker compose up -d redis postgres

# Rodar a API principal
docker compose up app

# Rodar o Worker de processamento (pode ser escalonado)
docker compose up worker
```

## 💻 Execução para Desenvolvimento (Local)

Se estiver desenvolvendo e quiser rodar os serviços separadamente:

```bash
# 1. API de Análise
python -m app.services.contract_analysis_service --port 8001

# 2. Worker de Processamento
python -m app.services.contract_analysis_worker

# 3. Testar via CLI (Perguntar algo ao RAG)
python -m app.services.ask_service_cli "Qual o valor total deste contrato?"
```

## 📂 Estrutura do Projeto

- `app/controllers`: Handlers HTTP (BaseHTTPRequestHandler).
- `app/services`: Lógica de negócio e entrypoints dos serviços.
- `app/rag`: Engine de processamento de documentos, extração de texto e IA.
- `app/workers`: Gerenciamento da fila de tarefas com Redis.
- `app/helpers`: Funções utilitárias e validação de autenticação.

---
Desenvolvido para auditoria e análise inteligente de contratos.