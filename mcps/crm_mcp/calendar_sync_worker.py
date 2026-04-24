from __future__ import annotations

import argparse
import json

try:
    from .contatos import sync_calendar_links
except ImportError:  # pragma: no cover
    from contatos import sync_calendar_links


def main() -> None:
    parser = argparse.ArgumentParser(description="Worker de sincronização Google Calendar para MCP-CRM.")
    parser.add_argument("--limit", type=int, default=20, help="Máximo de registros por execução.")
    parser.add_argument(
        "--status-filter",
        default="pending_or_failed",
        choices=["pending_or_failed", "pending_sync", "failed_sync", "all"],
        help="Filtro de status para processar links.",
    )
    parser.add_argument("--calendar-id", default=None, help="Calendar ID destino (override do env GOOGLE_CALENDAR_ID).")
    args = parser.parse_args()

    result = sync_calendar_links(
        limit=args.limit,
        status_filter=args.status_filter,
        calendar_id=args.calendar_id,
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
