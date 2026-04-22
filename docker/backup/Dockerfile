FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    jq \
    sqlite3 \
    postgresql-client \
    unzip \
    && curl -fsSL https://downloads.rclone.org/rclone-current-linux-amd64.zip -o /tmp/rclone.zip \
    && unzip -q /tmp/rclone.zip -d /tmp/rclone-dist \
    && mv /tmp/rclone-dist/rclone-*-linux-amd64/rclone /usr/local/bin/rclone \
    && chmod +x /usr/local/bin/rclone \
    && rm -rf /tmp/rclone.zip /tmp/rclone-dist \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir apscheduler==3.10.4

COPY scripts/ /scripts/
RUN chmod +x /scripts/backup_db.sh /scripts/restore_db.sh

WORKDIR /app
COPY crons/ ./crons/

CMD ["python", "-m", "crons.mcp_backup_cron"]
