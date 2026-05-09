from __future__ import annotations

from mcps.crm_mcp import main


def test_rbac_denies_manager_only_operation(monkeypatch):
    audits = []
    monkeypatch.setattr(main, "_record_operation_audit", lambda **kwargs: audits.append(kwargs))

    req = main.CRMRequest(
        operation="approve_strategy_updates",
        proposal_batch_id="proposal-1",
        approver="ana",
        decision_notes="Ajustes aprovados para o proximo batch.",
        actor_id="user-1",
        actor_role="sales_agent",
    )
    result = main.execute_crm(req)

    assert "acesso negado" in result["result"]
    assert audits
    assert audits[0]["status"] == "denied"
    assert audits[0]["operation"] == "approve_strategy_updates"
    assert audits[0]["role"] == "sales_agent"


def test_rbac_requires_reason_for_critical_operation(monkeypatch):
    audits = []
    monkeypatch.setattr(main, "_record_operation_audit", lambda **kwargs: audits.append(kwargs))

    req = main.CRMRequest(
        operation="mark_no_interest",
        contact_id="contact-1",
        actor_id="user-2",
        actor_role="sales_agent",
    )
    result = main.execute_crm(req)

    assert "reason obrigatório" in result["result"]
    assert audits
    assert audits[0]["status"] == "denied"
    assert audits[0]["operation"] == "mark_no_interest"


def test_critical_operation_is_audited_when_successful(monkeypatch):
    audits = []
    monkeypatch.setattr(main, "_record_operation_audit", lambda **kwargs: audits.append(kwargs))
    monkeypatch.setattr(
        main,
        "approve_strategy_updates",
        lambda proposal_batch_id, approver, decision_notes=None: {
            "proposal": {"proposal_batch_id": proposal_batch_id, "status": "approved"},
            "applied_adjustments": 3,
        },
    )

    req = main.CRMRequest(
        operation="approve_strategy_updates",
        proposal_batch_id="proposal-2",
        approver="maria",
        decision_notes="Aplicar ajustes do reviewer.",
        actor_id="manager-1",
        actor_role="sales_manager",
    )
    result = main.execute_crm(req)

    assert result["result"]["applied_adjustments"] == 3
    assert audits
    assert audits[-1]["status"] == "success"
    assert audits[-1]["resource_id"] == "proposal-2"
    assert audits[-1]["role"] == "sales_manager"


def test_legacy_request_without_role_keeps_backward_compatibility(monkeypatch):
    audits = []
    monkeypatch.setattr(main, "_record_operation_audit", lambda **kwargs: audits.append(kwargs))
    monkeypatch.setattr(
        main,
        "mark_no_interest",
        lambda contact_id, reason=None, draft_interaction_id=None, metadata=None: {
            "contact": {"id": contact_id, "do_not_contact": True},
            "interaction": {"outcome": "no_interest"},
        },
    )

    req = main.CRMRequest(
        operation="mark_no_interest",
        contact_id="contact-legacy",
    )
    result = main.execute_crm(req)

    assert result["result"]["contact"]["do_not_contact"] is True
    assert audits
    assert audits[-1]["status"] == "success"
    assert audits[-1]["role"] == "system"
