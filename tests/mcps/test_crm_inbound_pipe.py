from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from pipes import crm_inbound_pipe


def _routing(intent: str, specialist: str, policy_flags: list[str] | None = None) -> dict:
    return {
        "intent": intent,
        "confidence": 0.9,
        "specialist": specialist,
        "policy_flags": policy_flags or [],
    }


def _buffer_flushed(text: str) -> dict:
    return {
        "status": "flushed",
        "grouped_count": 1,
        "flush_reason": "completeness",
        "payload": {"text": text, "messages": [text], "channel": "whatsapp"},
    }


def _buffer_open() -> dict:
    return {"status": "open", "grouped_count": 1, "flush_reason": None, "payload": None}


# ── buffering (mensagem ainda sendo agregada) ────────────────────────────────


def test_returns_buffering_when_buffer_still_open():
    with (
        patch.object(crm_inbound_pipe, "buffer_incoming_messages", return_value=_buffer_open()),
    ):
        result = crm_inbound_pipe.run(lead_id="lead-1", event_text="oi")

    assert result["status"] == "buffering"


# ── block_and_stop ───────────────────────────────────────────────────────────


def test_blocks_and_marks_no_interest_on_block_policy():
    mark_mock = MagicMock(return_value={"ok": True})
    with (
        patch.object(crm_inbound_pipe, "buffer_incoming_messages", return_value=_buffer_flushed("para")),
        patch.object(crm_inbound_pipe, "route_conversation_turn", return_value=_routing("no_interest", "handover-agent", ["block_and_stop"])),
        patch.object(crm_inbound_pipe, "log_conversation_event", return_value={}),
        patch.object(crm_inbound_pipe, "mark_no_interest", mark_mock),
    ):
        result = crm_inbound_pipe.run(lead_id="lead-1", event_text="para")

    assert result["status"] == "blocked"
    mark_mock.assert_called_once()


# ── pause_automation ─────────────────────────────────────────────────────────


def test_returns_paused_on_pause_automation_policy():
    with (
        patch.object(crm_inbound_pipe, "buffer_incoming_messages", return_value=_buffer_flushed("silencio")),
        patch.object(crm_inbound_pipe, "route_conversation_turn", return_value=_routing("proactive_follow_up", "qualifier-agent", ["pause_automation"])),
        patch.object(crm_inbound_pipe, "log_conversation_event", return_value={}),
    ):
        result = crm_inbound_pipe.run(lead_id="lead-1", event_text="silencio")

    assert result["status"] == "paused"


# ── happy path ───────────────────────────────────────────────────────────────


def test_dispatches_to_specialist_and_sends():
    fake_specialist = MagicMock()
    fake_specialist.respond.return_value = ["Oi pessoal, tudo bem?"]

    send_mock = MagicMock(return_value={"sent": True, "messages": ["Oi pessoal, tudo bem?"]})

    with (
        patch.object(crm_inbound_pipe, "buffer_incoming_messages", return_value=_buffer_flushed("oi tudo bem")),
        patch.object(crm_inbound_pipe, "route_conversation_turn", return_value=_routing("greeting", "qualifier-agent")),
        patch.object(crm_inbound_pipe, "log_conversation_event", return_value={}),
        patch.object(crm_inbound_pipe, "_load_specialist", return_value=fake_specialist),
        patch.object(crm_inbound_pipe, "send_whatsapp_outreach", send_mock),
    ):
        result = crm_inbound_pipe.run(lead_id="lead-1", event_text="oi tudo bem")

    assert result["status"] == "sent"
    assert result["intent"] == "greeting"
    assert result["specialist"] == "qualifier-agent"
    assert result["messages_count"] == 1
    fake_specialist.respond.assert_called_once()
    send_mock.assert_called_once()


# ── automation_runtime RBAC ──────────────────────────────────────────────────


def test_automation_runtime_role_can_call_process_inbound():
    from mcps.crm_mcp import main

    req = main.CRMRequest(
        operation="process_inbound_message",
        lead_id="lead-1",
        event_text="oi",
        actor_role="automation_runtime",
    )
    _, role = main._resolve_actor(req)
    allowed, reason = main._authorize_request(req, role=role)

    assert allowed is True, reason


def test_sales_operator_role_is_allowed():
    from mcps.crm_mcp import main

    req = main.CRMRequest(
        operation="send_whatsapp_outreach",
        contact_id="contact-1",
        actor_role="sales_operator",
    )
    _, role = main._resolve_actor(req)
    allowed, reason = main._authorize_request(req, role=role)

    assert allowed is True, reason
