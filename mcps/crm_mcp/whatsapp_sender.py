from __future__ import annotations

import os
import random
import re
import time
from typing import Any, Callable

import requests


def _normalize_phone(value: str) -> str:
    return re.sub(r"\D+", "", (value or "").strip())


def human_delay_ms(message: str) -> int:
    """40ms por caractere + jitter, clamp entre 1500ms e 8000ms."""
    base = len((message or "").strip()) * 40
    jitter = random.randint(-400, 600)
    return int(min(max(base + jitter, 1500), 8000))


def human_read_delay_ms(incoming_text: str | None = None) -> int:
    """Simula tempo de leitura humana da mensagem anterior.

    Regras:
    - 55ms por caractere + jitter
    - clamp entre 1200ms e 12000ms
    """
    normalized = (incoming_text or "").strip()
    base = len(normalized) * 55
    jitter = random.randint(-500, 900)
    return int(min(max(base + jitter, 1200), 12000))


def _send_via_evolution(number: str, message: str, delay_ms: int, timeout: int = 20) -> dict[str, Any]:
    base_url = (os.environ.get("EVOLUTION_URL") or "").strip().rstrip("/")
    instance = (os.environ.get("EVOLUTION_INSTANCE") or "").strip()
    api_key = (os.environ.get("EVOLUTION_API_KEY") or "").strip()
    if not (base_url and instance and api_key):
        raise RuntimeError("EVOLUTION_URL, EVOLUTION_INSTANCE e EVOLUTION_API_KEY são obrigatórios para envio via Evolution.")

    url = f"{base_url}/message/sendText/{instance}"
    payload = {
        "number": number,
        "text": message,
        "options": {
            "presence": "composing",
            "delay": delay_ms,
        },
    }
    response = requests.post(
        url,
        headers={
            "Content-Type": "application/json",
            "apikey": api_key,
        },
        json=payload,
        timeout=timeout,
    )
    ok = response.status_code in {200, 201}
    body: dict[str, Any]
    try:
        parsed = response.json()
        body = parsed if isinstance(parsed, dict) else {"raw": parsed}
    except Exception:
        body = {"raw": response.text[:2000]}
    return {
        "provider": "evolution",
        "ok": ok,
        "status_code": response.status_code,
        "response": body,
        "delay_ms": delay_ms,
        "presence": "composing",
    }


def _send_via_gateway(number: str, message: str, timeout: int = 20) -> dict[str, Any]:
    gateway_url = (os.environ.get("OPENCLAW_GATEWAY_URL") or os.environ.get("GATEWAY_URL") or "http://localhost:18789").strip().rstrip("/")
    token = (os.environ.get("OPENCLAW_GATEWAY_TOKEN") or os.environ.get("OPENCLAW_GATEWAY_PASSWORD") or "").strip()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    invoke_response = requests.post(
        f"{gateway_url}/tools/invoke",
        headers=headers,
        json={
            "tool": "message",
            "action": "send",
            "args": {
                "channel": "whatsapp",
                "target": number,
                "message": message,
            },
            "sessionKey": "main",
        },
        timeout=timeout,
    )
    if invoke_response.status_code in {200, 201}:
        return {
            "provider": "openclaw_gateway_tools_invoke",
            "ok": True,
            "status_code": invoke_response.status_code,
            "response": invoke_response.text[:2000],
        }

    legacy_response = requests.post(
        f"{gateway_url}/api/message",
        headers=headers,
        json={
            "channel": "whatsapp",
            "to": number,
            "content": message,
        },
        timeout=timeout,
    )
    return {
        "provider": "openclaw_gateway_api_message",
        "ok": legacy_response.status_code == 200,
        "status_code": legacy_response.status_code,
        "response": legacy_response.text[:2000],
    }


def send_whatsapp_messages(
    number: str,
    messages: list[str],
    *,
    pre_read_delay_ms: int = 0,
    timeout: int = 20,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    phone = _normalize_phone(number)
    if not phone:
        return {"error": "Número de WhatsApp inválido."}
    clean_messages = [(msg or "").strip() for msg in messages if (msg or "").strip()]
    if not clean_messages:
        return {"error": "Nenhuma mensagem para envio."}

    use_evolution = bool(
        (os.environ.get("EVOLUTION_URL") or "").strip()
        and (os.environ.get("EVOLUTION_INSTANCE") or "").strip()
        and (os.environ.get("EVOLUTION_API_KEY") or "").strip()
    )

    read_delay_applied_ms = max(int(pre_read_delay_ms or 0), 0)
    if read_delay_applied_ms > 0:
        sleep_fn(read_delay_applied_ms / 1000.0)

    details: list[dict[str, Any]] = []
    for message in clean_messages:
        delay_ms = human_delay_ms(message)
        try:
            if use_evolution:
                result = _send_via_evolution(phone, message, delay_ms=delay_ms, timeout=timeout)
            else:
                # Fallback: sem suporte nativo de presence no gateway.
                # Mantemos pausa local para preservar timing humano.
                sleep_fn(delay_ms / 1000.0)
                result = _send_via_gateway(phone, message, timeout=timeout)
                result["delay_ms"] = delay_ms
                result["presence"] = "local_delay_fallback"
                result["note"] = "Gateway sem presence nativo; aplicado delay local."
        except Exception as exc:
            result = {
                "provider": "evolution" if use_evolution else "openclaw_gateway",
                "ok": False,
                "error": str(exc),
                "delay_ms": delay_ms,
            }
        result["message"] = message
        details.append(result)
        if not result.get("ok"):
            break

    sent_count = sum(1 for item in details if item.get("ok"))
    return {
        "provider": "evolution" if use_evolution else "openclaw_gateway",
        "messages_total": len(clean_messages),
        "messages_sent": sent_count,
        "all_sent": sent_count == len(clean_messages),
        "read_delay_applied_ms": read_delay_applied_ms,
        "details": details,
    }
