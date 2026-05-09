from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from openclaw.user_preferences import UserPreferenceStore


def main() -> int:
    parser = argparse.ArgumentParser(description="Generic user preference storage (local + MemClaw).")
    sub = parser.add_subparsers(dest="cmd", required=True)

    set_p = sub.add_parser("set", help="Set a preference key/value")
    set_p.add_argument("--user-id", required=True)
    set_p.add_argument("--domain", default="general")
    set_p.add_argument("--key", required=True)
    set_p.add_argument("--value", required=True, help="JSON value or plain string")
    set_p.add_argument("--source", default="manual")

    get_p = sub.add_parser("get", help="Get preferences")
    get_p.add_argument("--user-id", required=True)
    get_p.add_argument("--domain")

    args = parser.parse_args()
    store = UserPreferenceStore()

    if args.cmd == "set":
        raw = args.value
        try:
            value = json.loads(raw)
        except Exception:
            value = raw
        result = store.set_preference(
            user_id=args.user_id,
            domain=args.domain,
            key=args.key,
            value=value,
            source=args.source,
        )
        print(json.dumps({"status": "ok", "saved": result}, ensure_ascii=False))
        return 0

    if args.cmd == "get":
        prefs = store.get_preferences(user_id=args.user_id, domain=args.domain)
        print(json.dumps({"status": "ok", "preferences": prefs}, ensure_ascii=False, indent=2))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
