FROM python:3.11-slim

# Evita ficheiros .pyc e garante logs em tempo real
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Instala curl (útil para healthchecks/debug) e limpa cache
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Instala as dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo o projeto (incluindo a pasta data/ com os JSONs)
COPY . .

EXPOSE 8000

# Comando padrão: inicia a aplicação web
CMD ["uvicorn", "web.backend.main:app", "--host", "0.0.0.0", "--port", "8000"]