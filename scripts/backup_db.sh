#!/bin/bash
# scripts/backup_db.sh
# Faz backup de todos os bancos/schemas e envia para o Google Drive usando rclone
# Requer: rclone configurado com remote "gdrive"

set -e

# Variáveis de ambiente esperadas
: "${PGHOST:?}"  # Host do Postgres
: "${PGUSER:?}"  # Usuário do Postgres
: "${PGPASSWORD:?}"  # Senha do Postgres
: "${GDRIVE_FOLDER_ID:?}"  # ID da pasta no Google Drive

BACKUP_DIR="/tmp/db_backups"
BACKUP_FILE="backup_$(date +%Y%m%d_%H%M%S).sql.gz"

mkdir -p "$BACKUP_DIR"

# Dump de todos os bancos/schemas
pg_dumpall -h "$PGHOST" -U "$PGUSER" | gzip > "$BACKUP_DIR/$BACKUP_FILE"

# Envia para o Google Drive usando rclone
rclone copy "$BACKUP_DIR/$BACKUP_FILE" "gdrive:${GDRIVE_FOLDER_ID}" --progress

# Limpa backups antigos (opcional, mantém só os últimos 7)
find "$BACKUP_DIR" -type f -mtime +7 -delete
