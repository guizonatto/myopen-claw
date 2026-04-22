"""
Script: model_usage_report.py
Função: Gera um relatório manual de uso de modelos a partir do SQLite local da telemetria.
Usar quando: Quiser inspecionar a última hora e o acumulado do dia sem depender do scheduler.

ENV_VARS:
  - MODEL_USAGE_DB_PATH: caminho do SQLite
  - MODEL_USAGE_REPORT_TIMEZONE: timezone operacional

DB_TABLES:
  - usage_events: leitura
  - report_dispatches: leitura
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from llm_usage_telemetry.dispatcher import build_reporting_windows
from llm_usage_telemetry.reporting import build_discord_report
from llm_usage_telemetry.settings import load_settings
from llm_usage_telemetry.storage import connect_db, initialize_schema, summarize_usage


def main() -> None:
    settings = load_settings()
    now_utc = datetime.now(timezone.utc)
    windows = build_reporting_windows(now_utc, settings.report_timezone)
    conn = connect_db(settings.db_path)
    initialize_schema(conn)
    try:
        last_hour_rows = summarize_usage(conn, windows.bucket_start_utc, windows.bucket_end_utc)
        day_rows = summarize_usage(conn, windows.day_start_utc, windows.bucket_end_utc)
        print(
            build_discord_report(
                last_hour_rows=last_hour_rows,
                day_rows=day_rows,
                timezone_name=settings.report_timezone,
                bucket_label=windows.bucket_label,
            )
        )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
