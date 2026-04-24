from __future__ import annotations

import argparse
import json

try:
    from .db import get_session
    from .improvement_report import send_daily_improvement_report
except ImportError:  # pragma: no cover
    from db import get_session
    from improvement_report import send_daily_improvement_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Worker de relatório diário de melhoria de estratégia no Discord.")
    parser.add_argument("--force", action="store_true", help="Ignora janela de horário (12:00 e 19:00 BRT).")
    parser.add_argument("--channel-id", default=None, help="Discord channel ID explícito.")
    parser.add_argument("--target", default=None, help="Target do gateway (ex: channel:sales-bot-improvement).")
    args = parser.parse_args()

    with get_session() as session:
        result = send_daily_improvement_report(
            session,
            force=args.force,
            channel_id=args.channel_id,
            target=args.target,
        )
        print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
