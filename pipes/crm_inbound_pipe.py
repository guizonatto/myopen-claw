"""
Pipe: crm_inbound_pipe
Função: Orquestra o pipeline de inbound CRM: buffer → roteamento → specialist → envio.
Usar quando: chega mensagem de WhatsApp inbound de um lead conhecido.

ENV_VARS:
  (nenhuma) — usa a sessão de DB configurada no mcp-crm

DB_TABLES:
  - crm_mcp.contatos: leitura
  - crm_mcp.incoming_message_buffers: leitura+escrita
  - crm_mcp.contact_interactions: leitura+escrita
"""
from __future__ import annotations

import importlib
from typing import Any

try:
    from mcps.crm_mcp.contatos import (
        buffer_incoming_messages,
        log_conversation_event,
        mark_no_interest,
        route_conversation_turn,
        send_whatsapp_outreach,
        transcribe_incoming_audio,
    )
except ImportError:  # pragma: no cover
    from contatos import (
        buffer_incoming_messages,
        log_conversation_event,
        mark_no_interest,
        route_conversation_turn,
        send_whatsapp_outreach,
        transcribe_incoming_audio,
    )

_SPECIALIST_MAP: dict[str, str] = {
    # current OpenClaw agent IDs
    "zind-crm-cold-contact": "agents.crm.qualifier_agent.QualifierAgent",
    "zind-crm-qualifier": "agents.crm.qualifier_agent.QualifierAgent",
    "zind-crm-closer": "agents.crm.closing_agent.ClosingAgent",
    "zind-crm-handover": "agents.crm.handover_agent.HandoverAgent",
    # legacy names kept for backward compatibility
    "qualifier-agent": "agents.crm.qualifier_agent.QualifierAgent",
    "objection-agent": "agents.crm.objection_agent.ObjectionAgent",
    "closing-agent": "agents.crm.closing_agent.ClosingAgent",
    "handover-agent": "agents.crm.handover_agent.HandoverAgent",
}


def run(
    *,
    lead_id: str,
    event_text: str,
    channel: str = "whatsapp",
    message_id: str | None = None,
    media_ref: str | None = None,
    is_audio: bool = False,
    max_hold_ms: int = 20000,
    max_msgs: int = 6,
    max_chars: int = 1000,
) -> dict[str, Any]:
    text = (event_text or "").strip()

    # Step 1 — transcribe audio
    if is_audio and media_ref:
        result = transcribe_incoming_audio(message_id=message_id or "auto", media_ref=media_ref)
        if "error" in result:
            return {"status": "error", "error": result["error"], "stage": "transcription"}
        text = result.get("text", text)

    # Step 2 — buffer (aggregate burst messages)
    buffered = buffer_incoming_messages(
        lead_id,
        text,
        channel=channel,
        message_id=message_id,
        max_hold_ms=max_hold_ms,
        max_msgs=max_msgs,
        max_chars=max_chars,
    )
    if "error" in buffered:
        return {"status": "error", "error": buffered["error"], "stage": "buffer"}

    if buffered.get("status") == "open":
        return {"status": "buffering", "grouped_count": buffered.get("grouped_count", 1)}

    # Step 3 — route
    payload = buffered.get("payload") or {}
    joined_text = (payload.get("text") or text).strip()
    route = route_conversation_turn({"text": joined_text, "is_audio": is_audio})
    if "error" in route:
        return {"status": "error", "error": route["error"], "stage": "routing"}

    intent = route["intent"]
    specialist_name = route["specialist"]
    policy_flags: list[str] = route.get("policy_flags") or []

    log_conversation_event(
        lead_id,
        channel=channel,
        direction="inbound",
        content_summary=joined_text[:500],
        intent=intent,
        metadata={"is_audio": is_audio, "policy_flags": policy_flags, "buffer_flush": buffered.get("flush_reason")},
    )

    # Step 4 — policy enforcement
    if "block_and_stop" in policy_flags:
        mark_no_interest(lead_id, reason="Solicitou remoção/sem interesse via mensagem inbound.")
        return {"status": "blocked", "intent": intent, "specialist": specialist_name}

    if "pause_automation" in policy_flags:
        return {
            "status": "paused",
            "intent": intent,
            "specialist": specialist_name,
            "reason": "72h sem resposta — automação pausada, revisão humana necessária.",
        }

    # Step 5 — dispatch to specialist
    try:
        specialist = _load_specialist(specialist_name)
    except Exception as exc:
        return {"status": "error", "error": str(exc), "stage": "dispatch"}

    messages = specialist.respond(
        routing=route,
        contact_id=lead_id,
        joined_text=joined_text,
        channel=channel,
    )
    if not messages:
        return {"status": "no_response", "intent": intent, "specialist": specialist_name}

    # Step 6 — send
    sent = send_whatsapp_outreach(
        lead_id,
        messages=messages,
        require_approved=False,
        incoming_text=joined_text,
        content_summary=f"Resposta automática [{intent}] via {specialist_name}.",
    )
    if "error" in sent:
        return {"status": "error", "error": sent["error"], "stage": "send"}

    return {
        "status": "sent",
        "intent": intent,
        "specialist": specialist_name,
        "messages_count": len(messages),
        "messages": messages,
    }


if __name__ == "__main__":
    import json
    import os

    demo = run(
        lead_id=os.environ.get("DEMO_LEAD_ID", ""),
        event_text="Oi, tudo bem?",
    )
    print(json.dumps(demo, ensure_ascii=False, indent=2))
