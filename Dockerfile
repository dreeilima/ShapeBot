# Usar imagem oficial Python
FROM python:3.11-slim

# Evitar que o Python gere arquivos .pyc e garanta logs imediatos
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Definir diretório de trabalho
WORKDIR /app

# Instalar dependências do sistema necessárias (psycopg2-binary, etc)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements e instalar
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar todo o código do projeto
COPY . .

# Expor a porta que será usada pela API (Koyeb injeta via env PORT)
EXPOSE 8001

# Comando para rodar o servidor híbrido
CMD ["python", "run.py"]
