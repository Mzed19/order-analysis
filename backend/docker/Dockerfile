FROM python:3.10-slim

# Evita logs estranhos do Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Diretório de trabalho
WORKDIR /app

# Dependências do sistema (mínimas)
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copia dependências primeiro (cache eficiente)
COPY requirements.txt .

RUN pip install -r requirements.txt

# Copia o projeto
COPY . .

CMD ["bash"]