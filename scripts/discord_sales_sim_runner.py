from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from openclaw.discord_sales_simulation import (
    DEFAULT_MAX_TURNS,
    DEFAULT_TIMEOUT_SECONDS,
    DiscordAPITransport,
    OpenClawCLIInvoker,
    SimulationParseError,
    SimulationStorage,
    command_examples,
    run_from_command,
)


def _configure_logging() -> None:
    level = (os.environ.get("SIM_LOG_LEVEL") or "INFO").upper()
    logging.basicConfig(level=level, format="%(levelname)s %(asctime)s %(message)s")


def main() -> int:
    _configure_logging()

    parser = argparse.ArgumentParser(description="Discord sales simulation runner (sales-sim x sindico-sim).")
    parser.add_argument("--command", required=True, help="Comando textual recebido no Discord (sim start ...).")
    parser.add_argument("--channel-id", default=None, help="Canal pai para criar a thread.")
    parser.add_argument("--source-message-id", default=None, help="Mensagem origem para abrir thread a partir da mensagem.")
    parser.add_argument("--max-turns", type=int, default=DEFAULT_MAX_TURNS)
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--storage-dir", default=None, help="Diretório para metadata/transcript da simulação.")
    parser.add_argument("--openclaw-bin", default=None, help="Binary do OpenClaw CLI.")
    args = parser.parse_args()

    parent_channel_id = (args.channel_id or os.environ.get("DISCORD_SALES_SIM_CHANNEL_ID") or "").strip()
    if not parent_channel_id:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "DISCORD channel ausente. Informe --channel-id ou DISCORD_SALES_SIM_CHANNEL_ID.",
                },
                ensure_ascii=False,
            )
        )
        return 2

    bot_token = (os.environ.get("DISCORD_BOT_TOKEN") or "").strip()
    if not bot_token:
        print(json.dumps({"ok": False, "error": "DISCORD_BOT_TOKEN ausente."}, ensure_ascii=False))
        return 2

    storage_dir = (
        args.storage_dir
        or os.environ.get("SALES_SIM_STORAGE_DIR")
        or "mcp-crm-data/simulations/discord-sales"
    )
    storage = SimulationStorage(base_dir=Path(storage_dir))
    transport = DiscordAPITransport(bot_token=bot_token)
    invoker = OpenClawCLIInvoker(openclaw_bin=args.openclaw_bin or os.environ.get("OPENCLAW_BIN") or "openclaw")

    try:
        result = run_from_command(
            command_text=args.command,
            parent_channel_id=parent_channel_id,
            source_message_id=args.source_message_id,
            max_turns=max(args.max_turns, 1),
            timeout_seconds=max(args.timeout_seconds, 30),
            publisher=transport,
            invoker=invoker,
            storage=storage,
        )
    except SimulationParseError as exc:
        examples = command_examples()
        validation = (
            f"Comando inválido: {exc}\n"
            f"Exemplo 1: {examples[0]}\n"
            f"Exemplo 2: {examples[1]}"
        )
        try:
            transport.send_message(channel_id=parent_channel_id, content=validation)
        except Exception:
            pass
        print(json.dumps({"ok": False, "error": str(exc), "examples": examples}, ensure_ascii=False))
        return 1
    except Exception as exc:
        logging.exception("Simulation runner failed")
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1

    print(json.dumps({"ok": True, "result": result}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
