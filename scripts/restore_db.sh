#!/bin/bash
# scripts/restore_db.sh
# Restaura backup de PostgreSQL, Qdrant e SQLite a partir do Google Drive
#
# USO:
#   BACKUP_TIMESTAMP=20260421_040000 ./restore_db.sh
#   (ou sem BACKUP_TIMESTAMP para listar backups disponíveis)

set -euo pipefail

: "${PGHOST:?PGHOST não definido}"
: "${PGUSER:?PGUSER não definido}"
: "${PGPASSWORD:?PGPASSWORD não definido}"
: "${GDRIVE_FOLDER_ID:?GDRIVE_FOLDER_ID não definido}"

QDRANT_URL="${QDRANT_URL:-http://qdrant:6333}"
QDRANT_COLLECTION="${QDRANT_COLLECTION:-cortex_memories}"
SQLITE_PATH="${MODEL_USAGE_DB_PATH:-/data/llm-usage.sqlite3}"
RESTORE_DIR="/tmp/db_restore"

# Listar backups disponíveis se não informado timestamp
if [ -z "${BACKUP_TIMESTAMP:-}" ]; then
    echo "[RESTORE] Backups disponíveis no Google Drive:"
    rclone ls "gdrive:${GDRIVE_FOLDER_ID}/" | sort
    echo ""
    echo "Execute com: BACKUP_TIMESTAMP=YYYYMMDD_HHMMSS ./restore_db.sh"
    exit 0
fi

echo "[RESTORE] Restaurando backup de ${BACKUP_TIMESTAMP}..."
mkdir -p "$RESTORE_DIR"

# --- Baixar arquivos do Google Drive ---
echo "[RESTORE] Baixando arquivos..."
rclone copy "gdrive:${GDRIVE_FOLDER_ID}/" "$RESTORE_DIR/" \
    --include "*_${BACKUP_TIMESTAMP}*" \
    --log-level INFO

# --- Restaurar PostgreSQL ---
PG_DUMP="$RESTORE_DIR/postgres_${BACKUP_TIMESTAMP}.sql.gz"
if [ -f "$PG_DUMP" ]; then
    echo "[RESTORE] Restaurando PostgreSQL..."
    echo "  ATENÇÃO: isso vai sobrescrever o banco atual. Ctrl+C para cancelar (5s)..."
    sleep 5
    PGPASSWORD="$PGPASSWORD" gunzip -c "$PG_DUMP" | psql -h "$PGHOST" -U "$PGUSER" postgres
    echo "[RESTORE] PostgreSQL OK."
else
    echo "[RESTORE] postgres_${BACKUP_TIMESTAMP}.sql.gz não encontrado, pulando."
fi

# --- Restaurar Qdrant ---
QDRANT_SNAP="$RESTORE_DIR/qdrant_${BACKUP_TIMESTAMP}.snapshot"
if [ -f "$QDRANT_SNAP" ]; then
    echo "[RESTORE] Restaurando Qdrant snapshot..."
    # Faz upload do snapshot e recupera a coleção
    curl -sf -X POST "${QDRANT_URL}/collections/${QDRANT_COLLECTION}/snapshots/recover" \
        -H "Content-Type: multipart/form-data" \
        -F "snapshot=@${QDRANT_SNAP}"
    echo "[RESTORE] Qdrant OK."
else
    echo "[RESTORE] qdrant_${BACKUP_TIMESTAMP}.snapshot não encontrado, pulando."
fi

# --- Restaurar SQLite ---
SQLITE_DUMP="$RESTORE_DIR/llm_metrics_${BACKUP_TIMESTAMP}.sql.gz"
if [ -f "$SQLITE_DUMP" ]; then
    echo "[RESTORE] Restaurando SQLite..."
    [ -f "$SQLITE_PATH" ] && cp "$SQLITE_PATH" "${SQLITE_PATH}.bak"
    gunzip -c "$SQLITE_DUMP" | sqlite3 "$SQLITE_PATH"
    echo "[RESTORE] SQLite OK."
else
    echo "[RESTORE] llm_metrics_${BACKUP_TIMESTAMP}.sql.gz não encontrado, pulando."
fi

# --- Limpeza ---
rm -rf "$RESTORE_DIR"
echo "[RESTORE] Restauração concluída."
