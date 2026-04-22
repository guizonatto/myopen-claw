"""
Cron: mcp_backup_cron
Função: Executa backup diário de PostgreSQL, Qdrant e SQLite para Google Drive
        e VACUUM do SQLite 2x/dia (06h e 18h)
Usar quando: Agendamento automático de backup dos MCPs (roda às 4h diariamente)

ENV_VARS:
  - GDRIVE_FOLDER_ID: ID da pasta no Google Drive (obrigatório)
  - BACKUP_ENABLED: "true" para habilitar (default: true)
  - BACKUP_RETENTION_DAYS: dias de retenção (default: 7)
  - PGHOST, PGUSER, PGPASSWORD: credenciais PostgreSQL
  - MODEL_USAGE_DB_PATH: caminho do SQLite (default: /data/llm-usage.sqlite3)
  - TELEGRAM_BOT_TOKEN: token do bot Telegram para alertas de erro
  - TELEGRAM_USER_ID: ID do usuário Telegram para receber alertas
  - DISCORD_BOT_TOKEN: token do bot Discord para alertas de erro
  - DISCORD_ALERT_CHANNEL_ID: ID do canal Discord (Geral) para alertas

DB_TABLES:
  - (nenhuma — leitura via pg_dump externo)
"""
import os
import subprocess
import urllib.request
import urllib.parse
import json
from apscheduler.schedulers.blocking import BlockingScheduler


def _notify_telegram(message: str):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    user_id = os.environ.get("TELEGRAM_USER_ID", "")
    if not token or not user_id:
        return
    try:
        data = json.dumps({"chat_id": user_id, "text": message}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"[NOTIFY] Telegram falhou: {e}")


def _notify_discord(message: str):
    token = os.environ.get("DISCORD_BOT_TOKEN", "")
    channel_id = os.environ.get("DISCORD_ALERT_CHANNEL_ID", "")
    if not token or not channel_id:
        return
    try:
        data = json.dumps({"content": message}).encode()
        req = urllib.request.Request(
            f"https://discord.com/api/v10/channels/{channel_id}/messages",
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bot {token}",
            },
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"[NOTIFY] Discord falhou: {e}")


def notify_error(message: str):
    print(f"[NOTIFY] {message}")
    _notify_telegram(message)
    _notify_discord(message)


def job():
    backup_enabled = os.environ.get("BACKUP_ENABLED", "true").lower()
    if backup_enabled != "true":
        print("[BACKUP] Desabilitado via BACKUP_ENABLED.")
        return

    vacuum_sqlite()

    result = subprocess.run(
        ["/scripts/backup_db.sh"],
        capture_output=True,
        text=True,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(f"[BACKUP ERROR] {result.stderr}")
        notify_error(f"🔴 BACKUP FALHOU\n{result.stderr[-1000:]}")
    else:
        print("[BACKUP] Concluído com sucesso.")


def vacuum_sqlite():
    db_path = os.environ.get("MODEL_USAGE_DB_PATH", "/data/llm-usage.sqlite3")
    result = subprocess.run(
        ["sqlite3", db_path, "VACUUM;"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"[VACUUM ERROR] SQLite: {result.stderr}")
        notify_error(f"🔴 VACUUM SQLite FALHOU\n{result.stderr[-500:]}")
    else:
        print(f"[VACUUM] SQLite OK ({db_path})")


if __name__ == "__main__":
    scheduler = BlockingScheduler(timezone="America/Sao_Paulo")
    scheduler.add_job(job, "cron", hour=4, minute=0, id="mcp_backup")
    scheduler.add_job(vacuum_sqlite, "cron", hour=6, minute=0, id="vacuum_sqlite_morning")
    scheduler.add_job(vacuum_sqlite, "cron", hour=18, minute=0, id="vacuum_sqlite_evening")
    print("[BACKUP] Cron agendado: diariamente às 04:00 (America/Sao_Paulo)")
    print("[VACUUM] SQLite agendado: 06:00 e 18:00 (America/Sao_Paulo)")
    scheduler.start()
