FROM python:3.12-slim

WORKDIR /app

# Instalar dependências do sistema necessárias para psycopg2 e psql
RUN apt-get update && apt-get install -y gcc libpq-dev postgresql-client && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --break-system-packages -r requirements.txt

COPY . .

# Expor porta
EXPOSE 8003

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
