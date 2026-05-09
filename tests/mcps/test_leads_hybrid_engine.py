from __future__ import annotations

import json
from pathlib import Path

from mcps.leads_mcp import main as leads_main


def _write_state(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_run_sindico_leads_fallback_to_last_plan_when_optimizer_fails(monkeypatch, tmp_path):
    state_path = tmp_path / "leads_state.json"
    monkeypatch.setenv("LEADS_STATE_PATH", str(state_path))

    prior_plan = leads_main._build_baseline_plan(tenant_id="tenant_a", city="São Paulo", max_results=5)
    _write_state(
        state_path,
        {
            "plans": {"tenant_a": prior_plan},
            "history": {},
            "optimizer_failures": {},
        },
    )

    def _fake_collect(query_cfg, *, max_scan_results):
        return [
            leads_main.DiscoveredLead(
                name="Lead Teste",
                email="lead@example.com",
                whatsapp="+5511999999999",
                source_url="https://example.com/lead",
                source="duckduckgo_lite",
                query=str(query_cfg.get("id")),
            )
        ]

    monkeypatch.setattr(leads_main, "_collect_query_leads", _fake_collect)
    monkeypatch.setattr(leads_main, "_upsert_lead_into_crm", lambda lead: ("id-1", True, False))
    monkeypatch.setattr(leads_main, "_build_search_plan", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("429")))

    result = leads_main.run_sindico_leads({"tenant_id": "tenant_a", "city": "São Paulo", "max_results": 5})

    assert result["tenant_id"] == "tenant_a"
    assert result["leads_discovered"] >= 1
    assert result["optimizer_status"] == "fallback"
    assert str(result["fallback_reason"]).startswith("optimizer_failure:")
    assert result["search_plan"]["meta"]["fallback_reason"] is not None


def test_run_sindico_leads_keeps_state_isolated_per_tenant(monkeypatch, tmp_path):
    state_path = tmp_path / "leads_state.json"
    monkeypatch.setenv("LEADS_STATE_PATH", str(state_path))

    monkeypatch.setattr(leads_main, "_collect_query_leads", lambda query_cfg, *, max_scan_results: [])
    monkeypatch.setattr(leads_main, "_build_search_plan", lambda **kwargs: leads_main._build_baseline_plan(
        tenant_id=kwargs["tenant_id"],
        city=kwargs["city"],
        max_results=kwargs["max_results"],
    ))

    leads_main.run_sindico_leads({"tenant_id": "tenant_a", "city": "São Paulo", "max_results": 3})
    leads_main.run_sindico_leads({"tenant_id": "tenant_b", "city": "Rio de Janeiro", "max_results": 3})

    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert "tenant_a" in state["plans"]
    assert "tenant_b" in state["plans"]
    plan_a_text = state["plans"]["tenant_a"]["queries"][0]["text"].lower()
    plan_b_text = state["plans"]["tenant_b"]["queries"][0]["text"].lower()
    assert "são paulo" in plan_a_text
    assert "rio de janeiro" in plan_b_text


def test_heuristic_optimizer_limits_new_queries_and_preserves_baseline():
    previous = leads_main._build_baseline_plan(tenant_id="tenant_x", city="Curitiba", max_results=10)
    outcome = {
        "city": "Curitiba",
        "max_results": 10,
        "query_metrics": [
            {"query_id": "baseline_1", "discovered": 2, "dup_rate": 0.1},
            {"query_id": "baseline_2", "discovered": 1, "dup_rate": 0.2},
            {"query_id": "baseline_3", "discovered": 0, "dup_rate": 0.9},
        ],
    }
    optimized = leads_main._heuristic_optimize_plan(
        tenant_id="tenant_x",
        previous_plan=previous,
        outcome=outcome,
    )
    assert optimized["queries"]
    # com 2 mantidas, adição máxima fica em 1 (30%)
    assert len(optimized["queries"]) <= 3
