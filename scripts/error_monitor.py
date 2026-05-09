"""
Script: error_monitor
Função: Monitora logs dos containers OpenClaw e envia alertas no Discord quando detecta erros.
Usar quando: rodando como processo contínuo no background (via entrypoint.sh ou cron).

ENV_VARS:
  - DISCORD_ALERT_CHANNEL_ID: canal Discord para alertas de erro
  - OPENCLAW_GATEWAY_URL: URL do gateway (default: http://openclaw-gateway:18789)
  - ERROR_MONITOR_CONTAINERS: lista separada por vírgula (default: openclaw-gateway,llm-metrics-proxy,mcp-crm)
  - ERROR_MONITOR_COOLDOWN_S: segundos entre alertas do mesmo tipo (default: 120)
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone

try:
    import requests as _requests_lib
    _HAS_REQUESTS = True
except ImportError:
    import urllib.request as _urllib_request
    import json as _json_lib
    _HAS_REQUESTS = False

WEBHOOK_URL = os.environ.get("DISCORD_ERROR_WEBHOOK_URL", "")
CONTAINERS = os.environ.get("ERROR_MONITOR_CONTAINERS", "openclaw-gateway,llm-metrics-proxy,mcp-crm").split(",")
COOLDOWN_S = int(os.environ.get("ERROR_MONITOR_COOLDOWN_S", "120"))

# Padrões de erro e sua severidade/label
ERROR_PATTERNS = [
    # Falha total de todos os modelos — mais crítico
    (re.compile(r"FailoverError.*HTTP 500|FailoverError.*provider rejected|FailoverError.*network connection"), "🔴 FailoverError", "critical"),
    # Sessão travada
    (re.compile(r"stalled session.*classification=stalled"), "🟠 Sessão travada", "warning"),
    # Schema/tool rejeitado por provider
    (re.compile(r"provider rejected the request schema or tool payload"), "🟡 Schema rejeitado", "warning"),
    # PG connection perdida
    (re.compile(r"pg.*failed.*connection already closed|pg connect failed"), "🔴 PG desconectado", "critical"),
    # Container crash / fatal
    (re.compile(r"fatal|FATAL|Traceback.*Error|unhandled.*exception", re.IGNORECASE), "🔴 Erro fatal", "critical"),
    # Evolution API desconectada
    (re.compile(r"evolution.*close|whatsapp.*disconnect|instance.*close"), "🟠 WhatsApp desconectado", "warning"),
    # Rate limit total (todos providers)
    (re.compile(r"FailoverError.*rate limit|FailoverError.*429"), "🟡 Rate limit geral", "info"),
]

# Chave → último timestamp enviado (cooldown por tipo+container)
_last_sent: dict[str, float] = defaultdict(float)
_TOKENS_PER_CHAR_ESTIMATE = 0.3


def _extract_rate_limit_context(line: str) -> tuple[str | None, str | None]:
    """Extrai provider/model de linhas de log de rate limit, quando disponíveis."""
    provider = None
    model = None

    provider_patterns = [
        re.compile(r"(?:provider|providerName|target_provider|x-target-provider)[=:]\s*['\"]?([a-zA-Z0-9_.-]+)", re.IGNORECASE),
    ]
    model_patterns = [
        re.compile(r"(?:model|modelRef|targetModel|target_model|x-target-model)[=:]\s*['\"]?([a-zA-Z0-9_./:-]+)", re.IGNORECASE),
    ]
    pair_patterns = [
        re.compile(r"(?:upstream|target|model_ref)[=:]\s*['\"]?(?:usage-router/)?([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_./:-]+)", re.IGNORECASE),
        re.compile(r"\busage-router/([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_./:-]+)\b", re.IGNORECASE),
    ]

    for pattern in pair_patterns:
        pair_match = pattern.search(line)
        if pair_match:
            provider = provider or pair_match.group(1)
            model = model or pair_match.group(2)

    for pattern in provider_patterns:
        provider_match = pattern.search(line)
        if provider_match:
            provider = provider or provider_match.group(1)
            break

    for pattern in model_patterns:
        model_match = pattern.search(line)
        if model_match:
            model = model or model_match.group(1)
            break

    if (not provider or not model) and model:
        # Se vier model no formato provider/model, separa automaticamente.
        if "/" in model and not model.lower().startswith("http"):
            parts = model.split("/", 1)
            if len(parts) == 2 and parts[0] and parts[1]:
                provider = provider or parts[0]
                model = parts[1]

    return provider, model


def _extract_prompt_metrics(line: str) -> tuple[int | None, int | None]:
    """Extrai métricas de prompt do log; se faltar token, estima via 0.3 token/char."""
    chars = None
    tokens = None

    chars_patterns = [
        re.compile(r"prompt_chars[=:]\s*(\d+)", re.IGNORECASE),
        re.compile(r"input_chars[=:]\s*(\d+)", re.IGNORECASE),
        re.compile(r"\bchars[=:]\s*(\d+)", re.IGNORECASE),
    ]
    token_patterns = [
        re.compile(r"prompt_tokens[=:]\s*(\d+)", re.IGNORECASE),
        re.compile(r"input_tokens[=:]\s*(\d+)", re.IGNORECASE),
        re.compile(r"\btokens[=:]\s*(\d+)", re.IGNORECASE),
    ]

    for pattern in chars_patterns:
        m = pattern.search(line)
        if m:
            chars = int(m.group(1))
            break

    for pattern in token_patterns:
        m = pattern.search(line)
        if m:
            tokens = int(m.group(1))
            break

    if chars is None:
        prompt_match = re.search(
            r"""["']?(?:prompt|input)["']?\s*:\s*["'](.+?)["']""",
            line,
            flags=re.IGNORECASE,
        )
        if prompt_match:
            chars = len(prompt_match.group(1))

    if tokens is None and chars is not None:
        tokens = max(1, int(round(chars * _TOKENS_PER_CHAR_ESTIMATE)))

    return chars, tokens


def _send_alert(container: str, label: str, line: str, severity: str) -> None:
    if not WEBHOOK_URL:
        print(f"[error_monitor] DISCORD_ERROR_WEBHOOK_URL não configurado. Alerta: {label}", file=sys.stderr)
        return

    key = f"{container}:{label}"
    now = time.time()
    if now - _last_sent[key] < COOLDOWN_S:
        return  # cooldown ativo
    _last_sent[key] = now

    ts = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
    snippet = line.strip()[:300]
    extra_context = ""
    if "rate limit" in label.lower():
        provider, model = _extract_rate_limit_context(line)
        details = []
        details.append(f"provider={provider or 'desconhecido'}")
        details.append(f"model={model or 'desconhecido'}")
        extra_context = "\n" + " | ".join(details)
    elif "provider" in line.lower() or "schema rejeitado" in label.lower():
        chars, tokens_est = _extract_prompt_metrics(line)
        details = []
        details.append(f"prompt_chars={chars if chars is not None else 'desconhecido'}")
        details.append(f"prompt_tokens_est={tokens_est if tokens_est is not None else 'desconhecido'}")
        extra_context = "\n" + " | ".join(details)

    msg = f"{label} **[{container}]** `{ts}`{extra_context}\n```\n{snippet}\n```"

    try:
        payload = {"content": msg}
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "OpenClawMonitor/1.0 (error alerting)",
        }
        if _HAS_REQUESTS:
            resp = _requests_lib.post(WEBHOOK_URL, json=payload, headers=headers, timeout=5)
            status = resp.status_code
            body = resp.text[:100]
        else:
            data = _json_lib.dumps(payload).encode()
            req = _urllib_request.Request(WEBHOOK_URL, data=data, headers=headers, method="POST")
            with _urllib_request.urlopen(req, timeout=5) as r:
                status = r.status
                body = r.read(100).decode(errors="replace")
        if status not in (200, 204):
            print(f"[error_monitor] Discord webhook failed {status}: {body}", file=sys.stderr)
    except Exception as exc:
        print(f"[error_monitor] Discord webhook error: {exc}", file=sys.stderr)


def _tail_container(container: str) -> None:
    """Inicia docker logs -f para um container e processa linha a linha."""
    cmd = ["docker", "logs", "-f", "--since", "0s", container]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    except Exception as exc:
        print(f"[error_monitor] Não foi possível monitorar {container}: {exc}", file=sys.stderr)
        return

    print(f"[error_monitor] Monitorando {container}...", flush=True)
    try:
        for line in proc.stdout:
            for pattern, label, severity in ERROR_PATTERNS:
                if pattern.search(line):
                    _send_alert(container, label, line, severity)
                    break
    except Exception as exc:
        print(f"[error_monitor] Leitura interrompida em {container}: {exc}", file=sys.stderr)
    finally:
        proc.kill()


def main() -> None:
    if not WEBHOOK_URL:
        print("[error_monitor] DISCORD_ERROR_WEBHOOK_URL não definido — alertas desativados.", file=sys.stderr)

    import threading
    threads = []
    for container in CONTAINERS:
        t = threading.Thread(target=_tail_container, args=(container.strip(),), daemon=True)
        t.start()
        threads.append(t)

    # Envia mensagem de inicialização
    if WEBHOOK_URL:
        _send_alert("system", "✅ Monitor iniciado", f"Monitorando: {', '.join(CONTAINERS)}", "info")

    try:
        while True:
            time.sleep(60)
            # Reinicia threads mortas
            for i, t in enumerate(threads):
                if not t.is_alive():
                    container = CONTAINERS[i].strip()
                    print(f"[error_monitor] Reiniciando monitor de {container}", file=sys.stderr)
                    nt = threading.Thread(target=_tail_container, args=(container,), daemon=True)
                    nt.start()
                    threads[i] = nt
    except KeyboardInterrupt:
        print("[error_monitor] Encerrado.", flush=True)


if __name__ == "__main__":
    main()
