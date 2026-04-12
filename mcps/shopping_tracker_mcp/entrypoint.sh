#!/bin/sh
set -e
# Garante que a extensão pgvector exista no banco/schema do MCP
PGVECTOR_SQL="CREATE EXTENSION IF NOT EXISTS vector;"
echo "Verificando/instalando extensão pgvector..."
psql "${DATABASE_URL}" -c "$PGVECTOR_SQL" || echo "Aviso: não foi possível criar extensão vector (pode já existir ou falta permissão)"
alembic upgrade head
exec uvicorn main:app --host 0.0.0.0 --port 8003 --reload
