from __future__ import annotations

import inspect

from mcps.crm_mcp import contatos


def test_router_layer_does_not_call_actions_directly():
    source = inspect.getsource(contatos.route_conversation_turn)
    forbidden_calls = [
        "send_whatsapp_outreach(",
        "schedule_contact_task(",
        "approve_strategy_updates(",
        "reject_strategy_updates(",
    ]

    for forbidden in forbidden_calls:
        assert forbidden not in source


def test_governance_layer_does_not_send_whatsapp_directly():
    source = inspect.getsource(contatos.generate_strategy_update_proposal)
    assert "send_whatsapp_outreach(" not in source
    assert "send_whatsapp_messages(" not in source


def test_dormant_followup_worker_creates_internal_event_only():
    source = inspect.getsource(contatos.evaluate_dormant_leads)
    assert '"deliver": False' in source
