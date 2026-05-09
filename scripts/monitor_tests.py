"""
Script: monitor_tests
Função: Executa testes em loop e mostra status consolidado por rodada.
Uso:
  python3 scripts/monitor_tests.py --interval 30 --max-runs 0 -- tests/mcps/test_leads_hybrid_engine.py tests/mcps/test_leads_proxy.py

Notas:
  - --max-runs 0 = infinito (até Ctrl+C)
  - Tudo após `--` é repassado ao pytest
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import datetime, timezone


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def main() -> int:
    parser = argparse.ArgumentParser(description="Monitor contínuo de testes pytest.")
    parser.add_argument("--interval", type=int, default=30, help="Intervalo (segundos) entre rodadas.")
    parser.add_argument("--max-runs", type=int, default=0, help="Número máximo de rodadas (0 = infinito).")
    parser.add_argument("pytest_args", nargs="*", help="Argumentos repassados ao pytest.")
    args = parser.parse_args()

    pytest_args = args.pytest_args or [
        "tests/mcps/test_leads_hybrid_engine.py",
        "tests/mcps/test_leads_proxy.py",
    ]
    cmd = [sys.executable, "-m", "pytest", "-q", *pytest_args]

    run = 0
    failures = 0
    while True:
        run += 1
        started = time.time()
        print(f"\n[monitor-tests] run={run} started={_utcnow()} cmd={' '.join(cmd)}", flush=True)
        proc = subprocess.run(cmd, text=True, capture_output=True)
        elapsed = time.time() - started

        if proc.returncode == 0:
            status = "PASS"
        else:
            status = "FAIL"
            failures += 1

        print(f"[monitor-tests] run={run} status={status} elapsed={elapsed:.2f}s failures={failures}", flush=True)
        if proc.stdout.strip():
            print(proc.stdout.strip(), flush=True)
        if proc.returncode != 0 and proc.stderr.strip():
            print(proc.stderr.strip(), flush=True)

        if args.max_runs > 0 and run >= args.max_runs:
            break
        time.sleep(max(1, args.interval))

    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
