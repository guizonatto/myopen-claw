from __future__ import annotations

from typing import Any

from mcps.crm_mcp.whatsapp_sender import human_delay_ms, human_read_delay_ms, send_whatsapp_messages


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, Any] | None = None, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text

    def json(self) -> dict[str, Any]:
        return self._payload


def test_human_delay_ms_clamped_min_and_max(monkeypatch):
    monkeypatch.setattr("mcps.crm_mcp.whatsapp_sender.random.randint", lambda a, b: -400)
    assert human_delay_ms("oi") == 1500

    monkeypatch.setattr("mcps.crm_mcp.whatsapp_sender.random.randint", lambda a, b: 600)
    assert human_delay_ms("x" * 1000) == 8000


def test_human_read_delay_ms_clamped_min_and_max(monkeypatch):
    monkeypatch.setattr("mcps.crm_mcp.whatsapp_sender.random.randint", lambda a, b: -500)
    assert human_read_delay_ms("oi") == 1200

    monkeypatch.setattr("mcps.crm_mcp.whatsapp_sender.random.randint", lambda a, b: 900)
    assert human_read_delay_ms("x" * 1000) == 12000


def test_send_whatsapp_messages_uses_evolution_presence_and_delay(monkeypatch):
    monkeypatch.setenv("EVOLUTION_URL", "http://evolution:8080")
    monkeypatch.setenv("EVOLUTION_INSTANCE", "usell-main")
    monkeypatch.setenv("EVOLUTION_API_KEY", "token-123")

    calls: list[tuple[str, dict[str, Any], dict[str, Any]]] = []

    def _fake_post(url: str, **kwargs: Any):
        calls.append((url, kwargs.get("headers", {}), kwargs.get("json", {})))
        return _FakeResponse(200, payload={"status": "PENDING", "key": {"id": "abc123"}})

    monkeypatch.setattr("mcps.crm_mcp.whatsapp_sender.requests.post", _fake_post)
    monkeypatch.setattr("mcps.crm_mcp.whatsapp_sender.random.randint", lambda a, b: 0)

    slept: list[float] = []
    result = send_whatsapp_messages(
        "5511999990000",
        ["Mensagem 1", "Mensagem 2"],
        sleep_fn=lambda sec: slept.append(sec),
    )

    assert result["all_sent"] is True
    assert result["messages_sent"] == 2
    assert result["provider"] == "evolution"
    assert len(calls) == 2
    assert slept == []
    for url, headers, payload in calls:
        assert url.endswith("/message/sendText/usell-main")
        assert headers["apikey"] == "token-123"
        assert payload["options"]["presence"] == "composing"
        assert 1500 <= payload["options"]["delay"] <= 8000
    assert result["read_delay_applied_ms"] == 0


def test_send_whatsapp_messages_applies_read_delay_before_sending(monkeypatch):
    monkeypatch.setenv("EVOLUTION_URL", "http://evolution:8080")
    monkeypatch.setenv("EVOLUTION_INSTANCE", "usell-main")
    monkeypatch.setenv("EVOLUTION_API_KEY", "token-123")
    monkeypatch.setattr("mcps.crm_mcp.whatsapp_sender.random.randint", lambda a, b: 0)

    calls: list[tuple[str, dict[str, Any], dict[str, Any]]] = []

    def _fake_post(url: str, **kwargs: Any):
        calls.append((url, kwargs.get("headers", {}), kwargs.get("json", {})))
        return _FakeResponse(200, payload={"status": "PENDING", "key": {"id": "abc123"}})

    monkeypatch.setattr("mcps.crm_mcp.whatsapp_sender.requests.post", _fake_post)
    slept: list[float] = []
    result = send_whatsapp_messages(
        "5511999990000",
        ["Resposta com delay de leitura"],
        pre_read_delay_ms=2400,
        sleep_fn=lambda sec: slept.append(sec),
    )

    assert result["all_sent"] is True
    assert result["read_delay_applied_ms"] == 2400
    assert slept == [2.4]
    assert len(calls) == 1


def test_send_whatsapp_messages_fallback_gateway_applies_local_delay(monkeypatch):
    monkeypatch.delenv("EVOLUTION_URL", raising=False)
    monkeypatch.delenv("EVOLUTION_INSTANCE", raising=False)
    monkeypatch.delenv("EVOLUTION_API_KEY", raising=False)
    monkeypatch.setenv("OPENCLAW_GATEWAY_URL", "http://gateway.local")
    monkeypatch.setattr("mcps.crm_mcp.whatsapp_sender.random.randint", lambda a, b: 0)

    calls: list[tuple[str, dict[str, Any]]] = []

    def _fake_post(url: str, **kwargs: Any):
        calls.append((url, kwargs.get("json", {})))
        return _FakeResponse(200, payload={"ok": True}, text="ok")

    monkeypatch.setattr("mcps.crm_mcp.whatsapp_sender.requests.post", _fake_post)
    slept: list[float] = []

    result = send_whatsapp_messages(
        "5511999990000",
        ["Mensagem gateway"],
        sleep_fn=lambda sec: slept.append(sec),
    )

    assert result["all_sent"] is True
    assert result["provider"] == "openclaw_gateway"
    assert result["read_delay_applied_ms"] == 0
    assert len(slept) == 1
    assert slept[0] >= 1.5
    assert len(calls) >= 1
    assert calls[0][0].endswith("/tools/invoke")
    assert calls[0][1]["args"]["channel"] == "whatsapp"
