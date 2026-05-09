"""
Script: monitor_leads_jobs
Função: Resume saúde de execução dos jobs de leads no openclaw-gateway.
Uso:
  python3 scripts/monitor_leads_jobs.py --since 2h
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import Counter


def _run(cmd: list[str]) -> str:
    out = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip() or "falha ao executar comando")
    # docker logs escreve frequentemente em stderr.
    return f"{out.stdout}\n{out.stderr}".strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Monitora execução dos jobs de leads no gateway.")
    parser.add_argument("--since", default="2h", help="Janela de logs Docker (ex: 30m, 2h, 1h30m).")
    args = parser.parse_args()

    try:
        logs = _run(["docker", "logs", "--since", args.since, "openclaw-gateway"])
    except Exception as exc:
        print(f"[erro] Não foi possível ler logs do openclaw-gateway: {exc}")
        return 2

    lines = logs.splitlines()
    lead_lines = [ln for ln in lines if "Lead Fetch and Enrich" in ln or "session:agent:leads:cron:" in ln]
    if not lead_lines:
        print(f"[monitor] Nenhum evento de leads encontrado na janela ({args.since}).")
        return 1

    reason_counter = Counter()
    agent_counter = Counter()
    run_ids = set()

    run_id_re = re.compile(r"run:([a-f0-9-]+)")
    agent_re = re.compile(r"session:agent:([a-z0-9_-]+):cron:", re.IGNORECASE)

    for ln in lead_lines:
        m_run = run_id_re.search(ln)
        if m_run:
            run_ids.add(m_run.group(1))
        m_agent = agent_re.search(ln)
        if m_agent:
            agent_counter[m_agent.group(1)] += 1

        low = ln.lower()
        if "rate limit" in low or "rpm_limit_exceeded" in low:
            reason_counter["rate_limit"] += 1
        elif "not have enough quota" in low or "exceeded your current quota" in low:
            reason_counter["quota"] += 1
        elif "provider rejected the request schema" in low:
            reason_counter["schema_or_tool_payload"] += 1
        elif "failovererror" in low:
            reason_counter["failover_other"] += 1

    print(f"[monitor] Janela: {args.since}")
    print(f"[monitor] Eventos de leads: {len(lead_lines)}")
    print(f"[monitor] Runs únicas (leads): {len(run_ids)}")
    if agent_counter:
        agent_bits = ", ".join(f"{k}={v}" for k, v in sorted(agent_counter.items()))
        print(f"[monitor] Distribuição por agente: {agent_bits}")
    if reason_counter:
        reason_bits = ", ".join(f"{k}={v}" for k, v in reason_counter.most_common())
        print(f"[monitor] Falhas por motivo: {reason_bits}")
    else:
        print("[monitor] Não foram identificadas falhas classificáveis.")

    # Sanity check do script real de fetch (sem depender de LLM/cron).
    try:
        probe = _run(
            ["docker", "exec", "openclaw-gateway", "sh", "-lc", "python3 /opt/openclaw-bootstrap/workspace/scripts/fetch_sindico_leads.py"]
        ).strip()
        print(f"[monitor] Probe fetch_sindico_leads.py: {probe}")
    except Exception as exc:
        print(f"[monitor] Probe fetch_sindico_leads.py falhou: {exc}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
