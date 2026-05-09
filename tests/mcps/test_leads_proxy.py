from __future__ import annotations

import json

from mcps.leads_mcp import proxy as leads_proxy


def test_leads_proxy_call_forwards_action_and_params(monkeypatch):
    captured = {}

    def _runner(action, params):
        captured["action"] = action
        captured["params"] = params
        return {"ok": True, "action": action}

    monkeypatch.setattr(leads_proxy, "_runner", _runner)
    result_raw = leads_proxy._call_leads("sindico_leads", {"tenant_id": "tenant_a"})
    result = json.loads(result_raw)

    assert captured["action"] == "sindico_leads"
    assert captured["params"]["tenant_id"] == "tenant_a"
    assert result["ok"] is True


def test_leads_proxy_returns_error_when_backend_unavailable(monkeypatch):
    monkeypatch.setattr(leads_proxy, "_runner", None)
    monkeypatch.setattr(leads_proxy, "_get_runner", lambda: None)
    result = json.loads(leads_proxy._call_leads("sindico_leads", {}))
    assert "error" in result
