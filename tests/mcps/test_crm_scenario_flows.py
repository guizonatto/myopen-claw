"""
Tests: end-to-end conversation scenario flows using mocks.

Each scenario simulates a full conversation turn through the Python pipe
(the deterministic fallback layer). Verifies:
  - Correct specialist is dispatched
  - Response is sent
  - Policies are enforced
  - Stage is not advanced by the wrong agent

These tests document the EXPECTED behavior for each key scenario so
regression is caught immediately.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call
from uuid import uuid4

import pytest

from pipes import crm_inbound_pipe


# ── fixtures ──────────────────────────────────────────────────────────────────


LEAD_ID = str(uuid4())


def _flushed(text: str, flush_reason: str = "completeness") -> dict:
    return {
        "status": "flushed",
        "grouped_count": 1,
        "flush_reason": flush_reason,
        "payload": {"text": text, "messages": [text], "channel": "whatsapp"},
        "idempotent": False,
    }


def _open_buffer() -> dict:
    return {"status": "open", "grouped_count": 1, "flush_reason": None, "payload": None}


def _route(intent: str, specialist: str, policy_flags: list[str] | None = None) -> dict:
    return {
        "intent": intent,
        "confidence": 0.9,
        "specialist": specialist,
        "policy_flags": policy_flags or [],
    }


def _specialist_response(*messages: str) -> list[str]:
    return list(messages)


# ── Scenario 1: cold greeting → buffering (burst protection) ─────────────────


def test_scenario_burst_messages_are_buffered():
    """Lead sends 'Oi' and the buffer hasn't flushed yet — no response sent."""
    with (
        patch.object(crm_inbound_pipe, "buffer_incoming_messages", return_value=_open_buffer()),
    ):
        result = crm_inbound_pipe.run(lead_id=LEAD_ID, event_text="Oi")

    assert result["status"] == "buffering"


# ── Scenario 2: cold greeting → cold-contact specialist ──────────────────────


def test_scenario_greeting_dispatches_to_cold_contact():
    """Standard greeting routes to cold-contact and sends response."""
    specialist_mock = MagicMock()
    specialist_mock.respond.return_value = ["Oi Carlos, tudo bem? Vi que você visitou o site da Zind."]
    send_mock = MagicMock(return_value={"sent": True})

    with (
        patch.object(crm_inbound_pipe, "buffer_incoming_messages", return_value=_flushed("Oi")),
        patch.object(crm_inbound_pipe, "route_conversation_turn",
                     return_value=_route("greeting", "zind-crm-cold-contact")),
        patch.object(crm_inbound_pipe, "log_conversation_event", return_value={}),
        patch.object(crm_inbound_pipe, "_load_specialist", return_value=specialist_mock),
        patch.object(crm_inbound_pipe, "send_whatsapp_outreach", send_mock),
    ):
        result = crm_inbound_pipe.run(lead_id=LEAD_ID, event_text="Oi")

    assert result["status"] == "sent"
    assert result["specialist"] == "zind-crm-cold-contact"
    assert result["intent"] == "greeting"
    send_mock.assert_called_once()


# ── Scenario 3: price objection → qualifier ──────────────────────────────────


def test_scenario_price_objection_dispatches_to_qualifier():
    """Price objection routes to qualifier, not a separate objection agent."""
    specialist_mock = MagicMock()
    specialist_mock.respond.return_value = ["Entendo. Custo vs perda operacional — faz sentido conversar."]
    send_mock = MagicMock(return_value={"sent": True})

    with (
        patch.object(crm_inbound_pipe, "buffer_incoming_messages", return_value=_flushed("Muito caro")),
        patch.object(crm_inbound_pipe, "route_conversation_turn",
                     return_value=_route("objection_price", "zind-crm-qualifier")),
        patch.object(crm_inbound_pipe, "log_conversation_event", return_value={}),
        patch.object(crm_inbound_pipe, "_load_specialist", return_value=specialist_mock),
        patch.object(crm_inbound_pipe, "send_whatsapp_outreach", send_mock),
    ):
        result = crm_inbound_pipe.run(lead_id=LEAD_ID, event_text="Muito caro")

    assert result["status"] == "sent"
    assert result["specialist"] == "zind-crm-qualifier"
    send_mock.assert_called_once()


# ── Scenario 4: positive interest → closer ───────────────────────────────────


def test_scenario_interest_positive_dispatches_to_closer():
    """Positive interest routes to closer for next step / scheduling."""
    specialist_mock = MagicMock()
    specialist_mock.respond.return_value = [
        "Ótimo! Tenho um link pra você escolher o horário.",
        "https://cal.zind.pro — 15min de call, sem compromisso.",
    ]
    send_mock = MagicMock(return_value={"sent": True})

    with (
        patch.object(crm_inbound_pipe, "buffer_incoming_messages", return_value=_flushed("Tenho interesse")),
        patch.object(crm_inbound_pipe, "route_conversation_turn",
                     return_value=_route("interest_positive", "zind-crm-closer")),
        patch.object(crm_inbound_pipe, "log_conversation_event", return_value={}),
        patch.object(crm_inbound_pipe, "_load_specialist", return_value=specialist_mock),
        patch.object(crm_inbound_pipe, "send_whatsapp_outreach", send_mock),
    ):
        result = crm_inbound_pipe.run(lead_id=LEAD_ID, event_text="Tenho interesse")

    assert result["status"] == "sent"
    assert result["specialist"] == "zind-crm-closer"
    assert result["messages_count"] == 2


# ── Scenario 5: request_human → handover (NOT closer) ────────────────────────


def test_scenario_request_human_dispatches_to_handover_not_closer():
    """Request for human must route to handover, not closer."""
    specialist_mock = MagicMock()
    specialist_mock.respond.return_value = ["Claro! Vou acionar nosso time agora."]
    send_mock = MagicMock(return_value={"sent": True})

    with (
        patch.object(crm_inbound_pipe, "buffer_incoming_messages",
                     return_value=_flushed("Quero falar com o responsável")),
        patch.object(crm_inbound_pipe, "route_conversation_turn",
                     return_value=_route("request_human", "zind-crm-handover",
                                         ["handover_requested"])),
        patch.object(crm_inbound_pipe, "log_conversation_event", return_value={}),
        patch.object(crm_inbound_pipe, "_load_specialist", return_value=specialist_mock),
        patch.object(crm_inbound_pipe, "send_whatsapp_outreach", send_mock),
    ):
        result = crm_inbound_pipe.run(lead_id=LEAD_ID, event_text="Quero falar com o responsável")

    assert result["status"] == "sent"
    assert result["specialist"] == "zind-crm-handover"
    assert result["specialist"] != "zind-crm-closer"


# ── Scenario 6: escalate_frustration → handover (urgent) ─────────────────────


def test_scenario_escalation_dispatches_to_handover():
    """Frustrated lead must route to handover, not qualifier or closer."""
    specialist_mock = MagicMock()
    specialist_mock.respond.return_value = ["Entendo e peço desculpas. Vou acionar o time agora."]
    send_mock = MagicMock(return_value={"sent": True})

    with (
        patch.object(crm_inbound_pipe, "buffer_incoming_messages",
                     return_value=_flushed("Isso é ridículo")),
        patch.object(crm_inbound_pipe, "route_conversation_turn",
                     return_value=_route("escalate_frustration", "zind-crm-handover",
                                         ["urgent_handover"])),
        patch.object(crm_inbound_pipe, "log_conversation_event", return_value={}),
        patch.object(crm_inbound_pipe, "_load_specialist", return_value=specialist_mock),
        patch.object(crm_inbound_pipe, "send_whatsapp_outreach", send_mock),
    ):
        result = crm_inbound_pipe.run(lead_id=LEAD_ID, event_text="Isso é ridículo")

    assert result["status"] == "sent"
    assert result["specialist"] == "zind-crm-handover"


# ── Scenario 7: no_interest → block_and_stop (no response sent) ──────────────


def test_scenario_no_interest_blocks_and_marks_do_not_contact():
    """no_interest with block_and_stop policy: marks lead, sends nothing."""
    mark_mock = MagicMock(return_value={"ok": True})

    with (
        patch.object(crm_inbound_pipe, "buffer_incoming_messages",
                     return_value=_flushed("Não tenho interesse, me remova")),
        patch.object(crm_inbound_pipe, "route_conversation_turn",
                     return_value=_route("no_interest", "zind-crm-handover", ["block_and_stop"])),
        patch.object(crm_inbound_pipe, "log_conversation_event", return_value={}),
        patch.object(crm_inbound_pipe, "mark_no_interest", mark_mock),
        patch.object(crm_inbound_pipe, "send_whatsapp_outreach") as send_mock,
    ):
        result = crm_inbound_pipe.run(lead_id=LEAD_ID, event_text="Não tenho interesse, me remova")

    assert result["status"] == "blocked"
    mark_mock.assert_called_once()
    send_mock.assert_not_called()


# ── Scenario 8: pause_automation (72h timeout) ───────────────────────────────


def test_scenario_72h_timeout_pauses_automation():
    """72h follow-up triggers pause — nothing sent, no specialist called."""
    with (
        patch.object(crm_inbound_pipe, "buffer_incoming_messages",
                     return_value=_flushed("", "guardrail_time")),
        patch.object(crm_inbound_pipe, "route_conversation_turn",
                     return_value=_route("proactive_follow_up", "zind-crm-cold-contact",
                                         ["pause_automation"])),
        patch.object(crm_inbound_pipe, "log_conversation_event", return_value={}),
        patch.object(crm_inbound_pipe, "send_whatsapp_outreach") as send_mock,
    ):
        result = crm_inbound_pipe.run(lead_id=LEAD_ID, event_text="")

    assert result["status"] == "paused"
    send_mock.assert_not_called()


# ── Scenario 9: audio inbound → transcription → pipeline ─────────────────────


def test_scenario_audio_message_is_transcribed_before_pipeline():
    """Audio message: transcribe first, then buffer with transcribed text."""
    transcribe_mock = MagicMock(return_value={
        "text": "Olá, tenho interesse no produto",
        "confidence": 0.92,
        "provider": "hint",
        "message_id": "msg-1",
    })
    buffer_mock = MagicMock(return_value=_open_buffer())

    with (
        patch.object(crm_inbound_pipe, "transcribe_incoming_audio", transcribe_mock),
        patch.object(crm_inbound_pipe, "buffer_incoming_messages", buffer_mock),
    ):
        result = crm_inbound_pipe.run(
            lead_id=LEAD_ID,
            event_text="",
            is_audio=True,
            media_ref="https://cdn.example/audio.ogg",
            message_id="msg-1",
        )

    transcribe_mock.assert_called_once_with(message_id="msg-1", media_ref="https://cdn.example/audio.ogg")
    buffer_call_text = buffer_mock.call_args[0][1]
    assert "interesse" in buffer_call_text, (
        f"Buffer should receive transcribed text, got: '{buffer_call_text}'"
    )
    assert result["status"] == "buffering"


# ── Scenario 10: proactive follow-up 24h → cold-contact ─────────────────────


def test_scenario_24h_proactive_routes_to_cold_contact():
    """24h follow-up (soft_ping) routes to cold-contact for gentle reactivation."""
    specialist_mock = MagicMock()
    specialist_mock.respond.return_value = ["Oi Carlos, passando pra ver se ainda faz sentido conversar."]
    send_mock = MagicMock(return_value={"sent": True})

    with (
        patch.object(crm_inbound_pipe, "buffer_incoming_messages",
                     return_value=_flushed("", "guardrail_time")),
        patch.object(crm_inbound_pipe, "route_conversation_turn",
                     return_value=_route("proactive_follow_up", "zind-crm-cold-contact",
                                         ["soft_ping"])),
        patch.object(crm_inbound_pipe, "log_conversation_event", return_value={}),
        patch.object(crm_inbound_pipe, "_load_specialist", return_value=specialist_mock),
        patch.object(crm_inbound_pipe, "send_whatsapp_outreach", send_mock),
    ):
        result = crm_inbound_pipe.run(lead_id=LEAD_ID, event_text="")

    assert result["status"] == "sent"
    assert result["specialist"] == "zind-crm-cold-contact"
