from __future__ import annotations

import argparse
import json

try:
    from .contatos import evaluate_dormant_leads
except ImportError:  # pragma: no cover
    from contatos import evaluate_dormant_leads


def main() -> int:
    parser = argparse.ArgumentParser(description="Worker de follow-up proativo (timeout_24h/48h/72h).")
    parser.add_argument("--limit", type=int, default=50, help="Quantidade máxima de contatos avaliados por execução.")
    parser.add_argument("--first-sla-hours", type=int, default=24)
    parser.add_argument("--second-sla-hours", type=int, default=48)
    parser.add_argument("--third-sla-hours", type=int, default=72)
    args = parser.parse_args()

    result = evaluate_dormant_leads(
        ruleset={
            "first_sla_hours": args.first_sla_hours,
            "second_sla_hours": args.second_sla_hours,
            "third_sla_hours": args.third_sla_hours,
        },
        limit=args.limit,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
