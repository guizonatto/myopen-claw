#!/bin/bash
# scripts/backup_db.sh
# Backup de PostgreSQL, Qdrant e SQLite → Google Drive via rclone
# Requer: rclone configurado com remote "gdrive"

set -euo pipefail

: "${PGHOST:?PGHOST não definido}"
: "${PGUSER:?PGUSER não definido}"
: "${PGPASSWORD:?PGPASSWORD não definido}"
: "${GDRIVE_FOLDER_ID:?GDRIVE_FOLDER_ID não definido}"

BACKUP_ENABLED="${BACKUP_ENABLED:-true}"
if [ "$BACKUP_ENABLED" != "true" ]; then
    echo "[BACKUP] Desabilitado via BACKUP_ENABLED. Encerrando."
    exit 0
fi

RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-7}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/tmp/db_backups/${TIMESTAMP}"
QDRANT_URL="${QDRANT_URL:-http://qdrant:6333}"
QDRANT_COLLECTION="${QDRANT_COLLECTION:-cortex_memories}"
SQLITE_PATH="${MODEL_USAGE_DB_PATH:-/data/llm-usage.sqlite3}"

mkdir -p "$BACKUP_DIR"

echo "[BACKUP] Iniciando backup em ${TIMESTAMP}..."

# --- PostgreSQL ---
echo "[BACKUP] Dumping PostgreSQL..."
PGPASSWORD="$PGPASSWORD" pg_dumpall -h "$PGHOST" -U "$PGUSER" \
    | gzip > "$BACKUP_DIR/postgres_${TIMESTAMP}.sql.gz"
echo "[BACKUP] PostgreSQL OK ($(du -sh "$BACKUP_DIR/postgres_${TIMESTAMP}.sql.gz" | cut -f1))"

# --- Qdrant snapshot ---
echo "[BACKUP] Criando snapshot do Qdrant (${QDRANT_COLLECTION})..."
SNAPSHOT_RESPONSE=$(curl -sf -X POST "${QDRANT_URL}/collections/${QDRANT_COLLECTION}/snapshots" \
    -H "Content-Type: application/json" || true)

if [ -n "$SNAPSHOT_RESPONSE" ]; then
    SNAPSHOT_NAME=$(echo "$SNAPSHOT_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['result']['name'])" 2>/dev/null || true)
    if [ -n "$SNAPSHOT_NAME" ]; then
        curl -sf "${QDRANT_URL}/collections/${QDRANT_COLLECTION}/snapshots/${SNAPSHOT_NAME}" \
            --output "$BACKUP_DIR/qdrant_${TIMESTAMP}.snapshot"
        echo "[BACKUP] Qdrant OK ($(du -sh "$BACKUP_DIR/qdrant_${TIMESTAMP}.snapshot" | cut -f1))"
    else
        echo "[BACKUP] Qdrant: resposta inesperada, pulando snapshot."
    fi
else
    echo "[BACKUP] Qdrant indisponível, pulando snapshot."
fi

# --- SQLite (LLM metrics) ---
if [ -f "$SQLITE_PATH" ]; then
    echo "[BACKUP] Dumping SQLite (${SQLITE_PATH})..."
    sqlite3 "$SQLITE_PATH" ".backup /tmp/llm_metrics_snap.db"
    gzip -c /tmp/llm_metrics_snap.db > "$BACKUP_DIR/llm_metrics_${TIMESTAMP}.db.gz"
    rm -f /tmp/llm_metrics_snap.db
    echo "[BACKUP] SQLite OK ($(du -sh "$BACKUP_DIR/llm_metrics_${TIMESTAMP}.db.gz" | cut -f1))"
else
    echo "[BACKUP] SQLite não encontrado em ${SQLITE_PATH}, pulando."
fi

# --- Upload para Google Drive ---
echo "[BACKUP] Enviando para Google Drive (folder: ${GDRIVE_FOLDER_ID})..."
rclone copy "$BACKUP_DIR/" "gdrive:" --drive-root-folder-id="${GDRIVE_FOLDER_ID}" --log-level INFO

echo "[BACKUP] Upload concluído."

# --- Limpeza local ---
rm -rf "$BACKUP_DIR"

# --- Limpeza remota (backups > RETENTION_DAYS dias) ---
echo "[BACKUP] Limpando backups remotos com mais de ${RETENTION_DAYS} dias..."
rclone delete "gdrive:" \
    --drive-root-folder-id="${GDRIVE_FOLDER_ID}" \
    --min-age "${RETENTION_DAYS}d" \
    --log-level INFO || true

echo "[BACKUP] Finalizado com sucesso."
