"""
Tests: intent routing — every intent maps to the correct OpenClaw agent.
No DB required. Pure unit tests against contatos.route_conversation_turn.
"""
from __future__ import annotations

import pytest
from mcps.crm_mcp.contatos import route_conversation_turn, INTENT_TO_SPECIALIST


# ── routing table completeness ───────────────────────────────────────────────


def test_all_specialist_values_are_openclaw_agent_ids():
    """No legacy agent name (qualifier-agent, objection-agent…) should remain."""
    legacy_names = {"qualifier-agent", "objection-agent", "closing-agent", "handover-agent"}
    for intent, specialist in INTENT_TO_SPECIALIST.items():
        assert specialist not in legacy_names, (
            f"Intent '{intent}' still maps to legacy name '{specialist}'"
        )


def test_all_specialists_are_known_openclaw_ids():
    valid_ids = {
        "zind-crm-cold-contact",
        "zind-crm-qualifier",
        "zind-crm-closer",
        "zind-crm-handover",
    }
    for intent, specialist in INTENT_TO_SPECIALIST.items():
        assert specialist in valid_ids, (
            f"Intent '{intent}' maps to unknown agent '{specialist}'"
        )


# ── cold-contact intents ─────────────────────────────────────────────────────


@pytest.mark.parametrize("text,system_event", [
    ("Oi", None),
    ("Olá", None),
    ("Boa tarde", None),
    ("", "timeout_24h"),
    ("", "timeout_48h"),
])
def test_cold_contact_intents_route_to_cold_contact(text, system_event):
    payload = {"text": text}
    if system_event:
        payload["system_event"] = system_event
    result = route_conversation_turn(payload)
    assert result["specialist"] == "zind-crm-cold-contact", (
        f"text='{text}' event='{system_event}' → specialist='{result['specialist']}' intent='{result['intent']}'"
    )


# ── qualifier intents ────────────────────────────────────────────────────────


@pytest.mark.parametrize("text,expected_intent", [
    ("Já temos fornecedor para isso", "objection_competitor"),
    ("Muito caro para nós", "objection_price"),
    ("Não tenho tempo agora", "objection_time"),
    ("Não sei se é confiável", "objection_trust"),
    ("Pode me mandar um vídeo", "request_proof"),
    ("Pode me mandar um artigo", "request_proof"),
    ("Já temos uma solução parecida em casa", "objection_already_has_solution"),
])
def test_qualifier_intents_route_to_qualifier(text, expected_intent):
    result = route_conversation_turn({"text": text})
    assert result["specialist"] == "zind-crm-qualifier", (
        f"text='{text}' got specialist='{result['specialist']}' intent='{result['intent']}'"
    )
    assert result["intent"] == expected_intent, (
        f"text='{text}' expected intent='{expected_intent}' got='{result['intent']}'"
    )


# ── closer intents ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("text,expected_intent", [
    ("Tenho interesse sim", "interest_positive"),
    ("Gostei, faz sentido para nós", "interest_positive"),
    ("Pode agendar uma reunião", "request_demo_or_meeting"),
    ("Quero uma demo", "request_demo_or_meeting"),
    ("Vamos agendar uma call rápida", "request_demo_or_meeting"),
])
def test_closer_intents_route_to_closer(text, expected_intent):
    result = route_conversation_turn({"text": text})
    assert result["specialist"] == "zind-crm-closer", (
        f"text='{text}' got specialist='{result['specialist']}' intent='{result['intent']}'"
    )
    assert result["intent"] == expected_intent


# ── handover intents ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("text,expected_intent", [
    ("Quero falar com uma pessoa real", "request_human"),
    ("Me coloca em contato com o responsável", "request_human"),
    ("Não tenho interesse, podem me remover", "no_interest"),
    ("Para de me mandar mensagem por favor", "no_interest"),
    ("Não quero mais contato", "no_interest"),
    ("Isso é ridículo, que absurdo", "escalate_frustration"),
    ("Estou frustrado com esse atendimento", "escalate_frustration"),
])
def test_handover_intents_route_to_handover(text, expected_intent):
    result = route_conversation_turn({"text": text})
    assert result["specialist"] == "zind-crm-handover", (
        f"text='{text}' got specialist='{result['specialist']}' intent='{result['intent']}'"
    )
    assert result["intent"] == expected_intent, (
        f"text='{text}' expected intent='{expected_intent}' got='{result['intent']}'"
    )


# ── policy flags ─────────────────────────────────────────────────────────────


def test_no_interest_has_block_and_stop_policy():
    result = route_conversation_turn({"text": "Não tenho interesse, me remove"})
    assert "block_and_stop" in result.get("policy_flags", [])


def test_request_human_has_handover_requested_policy():
    result = route_conversation_turn({"text": "Quero falar com uma pessoa real"})
    assert "handover_requested" in result.get("policy_flags", [])


def test_escalate_frustration_has_urgent_handover_policy():
    result = route_conversation_turn({"text": "Isso é ridículo, que absurdo"})
    assert "urgent_handover" in result.get("policy_flags", [])


def test_proactive_follow_up_has_soft_ping_policy():
    result = route_conversation_turn({"text": "", "system_event": "timeout_24h"})
    assert "soft_ping" in result.get("policy_flags", [])


# ── guard: escalation/handover never goes to closer or qualifier ─────────────


def test_escalate_frustration_never_routes_to_closer():
    result = route_conversation_turn({"text": "Isso é ridículo, que absurdo"})
    assert result["specialist"] != "zind-crm-closer"


def test_request_human_never_routes_to_qualifier():
    result = route_conversation_turn({"text": "Quero falar com o responsável"})
    assert result["specialist"] != "zind-crm-qualifier"


def test_greeting_never_routes_to_closer():
    result = route_conversation_turn({"text": "Oi"})
    assert result["specialist"] != "zind-crm-closer"


# ── competitor vs already_has_solution disambiguation ───────────────────────


def test_competitor_routes_to_qualifier():
    result = route_conversation_turn({"text": "Já uso outro sistema com contrato vigente"})
    assert result["specialist"] == "zind-crm-qualifier"
    assert result["intent"] == "objection_competitor"


def test_already_has_solution_routes_to_qualifier():
    result = route_conversation_turn({"text": "Já temos uma solução parecida em uso"})
    assert result["specialist"] == "zind-crm-qualifier"
    assert result["intent"] == "objection_already_has_solution"
