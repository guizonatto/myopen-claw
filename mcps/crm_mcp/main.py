from __future__ import annotations

import json
import logging
import sys
from typing import Any, AsyncGenerator, Literal, Optional

try:
    from pipes import crm_inbound_pipe
except ImportError:  # pragma: no cover
    crm_inbound_pipe = None  # type: ignore[assignment]

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import text

try:
    from .auth import verify_api_key
    from .contatos import (
        add_contato,
        approve_first_touch,
        approve_strategy_updates,
        buffer_incoming_messages,
        create_personalized_outreach_draft,
        enrich_contact_data,
        evaluate_dormant_leads,
        list_contacts_to_follow_up,
        log_conversation_event,
        mark_no_interest,
        qualify_contact_for_outreach,
        record_human_feedback,
        reject_strategy_updates,
        route_conversation_turn,
        schedule_contact_task,
        search_contatos,
        send_daily_improvement_report,
        send_whatsapp_outreach,
        start_feedback_review_session,
        sync_calendar_links,
        transcribe_incoming_audio,
        update_contato,
        verify_contact_data,
        generate_strategy_update_proposal,
    )
    from .db import get_session
    from .models import OperationAuditLog
except ImportError:  # pragma: no cover
    from auth import verify_api_key
    from contatos import (
        add_contato,
        approve_first_touch,
        approve_strategy_updates,
        buffer_incoming_messages,
        create_personalized_outreach_draft,
        enrich_contact_data,
        evaluate_dormant_leads,
        list_contacts_to_follow_up,
        log_conversation_event,
        mark_no_interest,
        qualify_contact_for_outreach,
        record_human_feedback,
        reject_strategy_updates,
        route_conversation_turn,
        schedule_contact_task,
        search_contatos,
        send_daily_improvement_report,
        send_whatsapp_outreach,
        start_feedback_review_session,
        sync_calendar_links,
        transcribe_incoming_audio,
        update_contato,
        verify_contact_data,
        generate_strategy_update_proposal,
    )
    from db import get_session
    from models import OperationAuditLog

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import TextContent, Tool
except ImportError:  # pragma: no cover
    Server = None
    stdio_server = None
    TextContent = None
    Tool = None

app = FastAPI()


@app.get("/health")
def health():
    try:
        with get_session() as session:
            session.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


class CRMRequest(BaseModel):
    operation: Literal[
        "add_contact",
        "search_contact",
        "update_contact",
        "list_contacts_to_follow_up",
        "verify_contact_data",
        "enrich_contact_data",
        "qualify_contact_for_outreach",
        "create_personalized_outreach_draft",
        "approve_first_touch",
        "send_whatsapp_outreach",
        "schedule_contact_task",
        "log_conversation_event",
        "mark_no_interest",
        "sync_calendar_links",
        "send_daily_improvement_report",
        "buffer_incoming_messages",
        "route_conversation_turn",
        "transcribe_incoming_audio",
        "evaluate_dormant_leads",
        "start_feedback_review_session",
        "record_human_feedback",
        "generate_strategy_update_proposal",
        "approve_strategy_updates",
        "reject_strategy_updates",
        "process_inbound_message",
    ]
    nome: Optional[str] = Field(default=None, description="Nome do contato")
    email: Optional[str] = Field(default=None)
    cnpj: Optional[str] = Field(default=None)
    cnaes: Optional[list[str]] = Field(default=None)
    query: Optional[str] = Field(default=None)
    contact_id: Optional[str] = Field(default=None)
    apelido: Optional[str] = Field(default=None)
    tipo: Optional[str] = Field(default=None)
    whatsapp: Optional[str] = Field(default=None)
    telefone: Optional[str] = Field(default=None)
    linkedin: Optional[str] = Field(default=None)
    instagram: Optional[str] = Field(default=None)
    empresa: Optional[str] = Field(default=None)
    cargo: Optional[str] = Field(default=None)
    setor: Optional[str] = Field(default=None)
    city: Optional[str] = Field(default=None)
    region: Optional[str] = Field(default=None)
    client_type: Optional[str] = Field(default=None)
    inferred_city: Optional[bool] = Field(default=None)
    inferred_region: Optional[bool] = Field(default=None)
    inferred_client_type: Optional[bool] = Field(default=None)
    pipeline_status: Optional[str] = Field(default=None)
    stage: Optional[str] = Field(default=None)
    icp_type: Optional[str] = Field(default=None)
    persona_profile: Optional[str] = Field(default=None)
    pain_hypothesis: Optional[str] = Field(default=None)
    recent_signal: Optional[str] = Field(default=None)
    offer_fit: Optional[str] = Field(default=None)
    preferred_tone: Optional[str] = Field(default=None)
    best_contact_window: Optional[str] = Field(default=None)
    readiness_status: Optional[str] = Field(default=None)
    needs_human_review: Optional[bool] = Field(default=None)
    do_not_contact: Optional[bool] = Field(default=None)
    do_not_contact_reason: Optional[str] = Field(default=None)
    nota: Optional[str] = Field(default=None)
    hours_since_last_contact: Optional[int] = Field(default=24)
    limit: Optional[int] = Field(default=10)
    mode: Optional[str] = Field(default="deep")
    source: Optional[str] = Field(default=None)
    confidence: Optional[float] = Field(default=0.8)
    evidence: Optional[str] = Field(default=None)
    divergence_whatsapp: Optional[bool] = Field(default=False)
    divergence_email: Optional[bool] = Field(default=False)
    divergence_company_or_cnpj: Optional[bool] = Field(default=False)
    attempts_without_response: Optional[int] = Field(default=0)
    intent_signal: Optional[int] = Field(default=None)
    channel: Optional[str] = Field(default="whatsapp")
    approved_by: Optional[str] = Field(default=None)
    draft_interaction_id: Optional[str] = Field(default=None)
    due_at: Optional[str] = Field(default=None)
    objective: Optional[str] = Field(default=None)
    owner: Optional[str] = Field(default=None)
    priority: Optional[str] = Field(default="medium")
    sla_hours: Optional[int] = Field(default=24)
    sync_calendar: Optional[bool] = Field(default=True)
    reminder_at: Optional[str] = Field(default=None)
    direction: Optional[str] = Field(default=None)
    content_summary: Optional[str] = Field(default=None)
    outcome: Optional[str] = Field(default=None)
    stage_hops: Optional[int] = Field(default=None)
    metadata: Optional[dict] = Field(default=None)
    reason: Optional[str] = Field(default=None)
    status_filter: Optional[str] = Field(default="pending_or_failed")
    calendar_id: Optional[str] = Field(default=None)
    force: Optional[bool] = Field(default=False)
    report_channel_id: Optional[str] = Field(default=None)
    target: Optional[str] = Field(default=None)
    messages: Optional[list[str]] = Field(default=None)
    require_approved: Optional[bool] = Field(default=True)
    incoming_text: Optional[str] = Field(default=None)
    simulate_read_delay: Optional[bool] = Field(default=True)
    read_delay_ms: Optional[int] = Field(default=None)
    lead_id: Optional[str] = Field(default=None)
    event_text: Optional[str] = Field(default=None)
    message_id: Optional[str] = Field(default=None)
    max_hold_ms: Optional[int] = Field(default=20000)
    max_msgs: Optional[int] = Field(default=6)
    max_chars: Optional[int] = Field(default=1000)
    payload: Optional[dict] = Field(default=None)
    system_event: Optional[str] = Field(default=None)
    is_audio: Optional[bool] = Field(default=False)
    media_ref: Optional[str] = Field(default=None)
    transcript_hint: Optional[str] = Field(default=None)
    ruleset: Optional[dict] = Field(default=None)
    batch_id: Optional[str] = Field(default=None)
    session_id: Optional[str] = Field(default=None)
    feedback_text: Optional[str] = Field(default=None)
    tags: Optional[list[str]] = Field(default=None)
    author: Optional[str] = Field(default="sales_reviewer")
    thread_ref: Optional[str] = Field(default=None)
    proposed_by: Optional[str] = Field(default="feedback-reviewer-agent")
    proposal_batch_id: Optional[str] = Field(default=None)
    approver: Optional[str] = Field(default=None)
    decision_notes: Optional[str] = Field(default=None)
    actor_id: Optional[str] = Field(default=None)
    actor_role: Optional[str] = Field(default=None)


def _wrap_result(result):
    if isinstance(result, dict) and "error" in result:
        return {"result": result["error"]}
    return {"result": result}


_ALLOW_ALL_ROLES = {"system", "sales_manager"}
_SALES_OPERATOR_OPS = {
    "add_contact",
    "search_contact",
    "update_contact",
    "list_contacts_to_follow_up",
    "verify_contact_data",
    "enrich_contact_data",
    "qualify_contact_for_outreach",
    "create_personalized_outreach_draft",
    "approve_first_touch",
    "send_whatsapp_outreach",
    "schedule_contact_task",
    "log_conversation_event",
    "mark_no_interest",
    "buffer_incoming_messages",
    "route_conversation_turn",
    "transcribe_incoming_audio",
}
_ROLE_ALLOWED_OPERATIONS: dict[str, set[str]] = {
    "sales_agent": _SALES_OPERATOR_OPS,
    "sales_operator": _SALES_OPERATOR_OPS,
    "automation_runtime": {
        "buffer_incoming_messages",
        "route_conversation_turn",
        "transcribe_incoming_audio",
        "log_conversation_event",
        "send_whatsapp_outreach",
        "mark_no_interest",
        "evaluate_dormant_leads",
        "process_inbound_message",
    },
    "feedback_reviewer": {
        "search_contact",
        "list_contacts_to_follow_up",
        "start_feedback_review_session",
        "record_human_feedback",
        "generate_strategy_update_proposal",
    },
    "ops_worker": {
        "evaluate_dormant_leads",
        "sync_calendar_links",
        "send_daily_improvement_report",
    },
}
_MANAGER_ONLY_OPERATIONS = {"approve_strategy_updates", "reject_strategy_updates"}
_CRITICAL_OPERATIONS = {
    "approve_first_touch",
    "mark_no_interest",
    "approve_strategy_updates",
    "reject_strategy_updates",
}


def _resolve_actor(req: CRMRequest) -> tuple[str, str]:
    role = (req.actor_role or "").strip().lower() or "system"
    actor = (
        (req.actor_id or "").strip()
        or (req.approved_by or "").strip()
        or (req.approver or "").strip()
        or (req.author or "").strip()
        or "system"
    )
    return actor, role


def _resolve_operation_reason(req: CRMRequest) -> str | None:
    if req.operation == "approve_strategy_updates":
        return (req.decision_notes or req.reason or "").strip() or None
    return (req.reason or "").strip() or None


def _authorize_request(req: CRMRequest, *, role: str) -> tuple[bool, str | None]:
    if role in _ALLOW_ALL_ROLES:
        return True, None
    allowed = _ROLE_ALLOWED_OPERATIONS.get(role)
    if allowed is None:
        return False, f"role '{role}' desconhecido."
    if req.operation in _MANAGER_ONLY_OPERATIONS:
        return False, f"operation '{req.operation}' exige role sales_manager."
    if req.operation not in allowed:
        return False, f"role '{role}' sem permissão para '{req.operation}'."
    if req.operation in _CRITICAL_OPERATIONS and not _resolve_operation_reason(req):
        return False, f"reason obrigatório para operação crítica '{req.operation}'."
    return True, None


def _json_or_none(payload: Any) -> str | None:
    if payload is None:
        return None
    try:
        return json.dumps(payload, ensure_ascii=False)
    except Exception:
        return None


def _record_operation_audit(
    *,
    actor: str,
    role: str,
    operation: str,
    resource_id: str | None,
    status: str,
    reason: str | None = None,
    before_payload: Any = None,
    after_payload: Any = None,
    error: str | None = None,
) -> None:
    try:
        with get_session() as session:
            session.add(
                OperationAuditLog(
                    actor=actor,
                    role=role,
                    operation=operation,
                    resource_id=resource_id,
                    status=status,
                    reason=reason,
                    before_json=_json_or_none(before_payload),
                    after_json=_json_or_none(after_payload),
                    error=error,
                )
            )
            session.flush()
    except Exception as exc:  # pragma: no cover
        logger.warning("Falha ao registrar auditoria de operação: %s", exc)


@app.post("/execute", dependencies=[Depends(verify_api_key)])
def execute_crm(req: CRMRequest):
    actor, role = _resolve_actor(req)
    is_allowed, denied_reason = _authorize_request(req, role=role)
    if not is_allowed:
        _record_operation_audit(
            actor=actor,
            role=role,
            operation=req.operation,
            resource_id=req.contact_id or req.lead_id or req.proposal_batch_id or req.session_id,
            status="denied",
            reason=_resolve_operation_reason(req),
            error=denied_reason,
        )
        return {"result": f"Erro: acesso negado ({denied_reason})"}

    if req.operation == "add_contact":
        if not req.nome:
            return {"result": "Erro: nome obrigatório para adicionar contato."}
        if not (req.email or req.whatsapp or req.telefone):
            return {"result": "Erro: informe pelo menos um contato (email, whatsapp ou telefone)."}
        contato_id = add_contato(
            nome=req.nome,
            apelido=req.apelido,
            tipo=req.tipo,
            telefone=req.telefone,
            whatsapp=req.whatsapp,
            email=req.email,
            linkedin=req.linkedin,
            instagram=req.instagram,
            empresa=req.empresa,
            cargo=req.cargo,
            setor=req.setor,
            city=req.city,
            region=req.region,
            client_type=req.client_type,
            cnpj=req.cnpj,
            cnaes=req.cnaes,
            notas=req.nota,
        )
        ident = req.email or req.whatsapp or req.telefone
        return {"result": f"Contato '{req.nome}' ({ident}) adicionado.", "id": contato_id}

    if req.operation == "search_contact":
        if not req.query:
            return {"result": "Erro: query obrigatória para busca."}
        return {"result": search_contatos(req.query)}

    if req.operation == "update_contact":
        if not req.contact_id:
            return {"result": "Erro: contact_id obrigatório para atualizar contato."}
        result = update_contato(
            contact_id=req.contact_id,
            apelido=req.apelido,
            tipo=req.tipo,
            whatsapp=req.whatsapp,
            email=req.email,
            telefone=req.telefone,
            linkedin=req.linkedin,
            instagram=req.instagram,
            empresa=req.empresa,
            cargo=req.cargo,
            setor=req.setor,
            city=req.city,
            region=req.region,
            client_type=req.client_type,
            inferred_city=req.inferred_city,
            inferred_region=req.inferred_region,
            inferred_client_type=req.inferred_client_type,
            pipeline_status=req.pipeline_status,
            stage=req.stage,
            icp_type=req.icp_type,
            persona_profile=req.persona_profile,
            pain_hypothesis=req.pain_hypothesis,
            recent_signal=req.recent_signal,
            offer_fit=req.offer_fit,
            preferred_tone=req.preferred_tone,
            best_contact_window=req.best_contact_window,
            readiness_status=req.readiness_status,
            needs_human_review=req.needs_human_review,
            do_not_contact=req.do_not_contact,
            do_not_contact_reason=req.do_not_contact_reason,
            nota=req.nota,
        )
        return _wrap_result(result)

    if req.operation == "list_contacts_to_follow_up":
        contacts = list_contacts_to_follow_up(
            hours_since_last_contact=req.hours_since_last_contact or 24,
            limit=req.limit or 10,
        )
        return {"result": contacts}

    if req.operation == "verify_contact_data":
        if not req.contact_id:
            return {"result": "Erro: contact_id obrigatório para verificação."}
        return _wrap_result(verify_contact_data(req.contact_id))

    if req.operation == "enrich_contact_data":
        if not req.contact_id:
            return {"result": "Erro: contact_id obrigatório para enriquecimento."}
        return _wrap_result(
            enrich_contact_data(
                contact_id=req.contact_id,
                mode=req.mode or "deep",
                source=req.source,
                confidence=req.confidence if req.confidence is not None else 0.8,
                evidence=req.evidence,
                divergence_whatsapp=bool(req.divergence_whatsapp),
                divergence_email=bool(req.divergence_email),
                divergence_company_or_cnpj=bool(req.divergence_company_or_cnpj),
            )
        )

    if req.operation == "qualify_contact_for_outreach":
        if not req.contact_id:
            return {"result": "Erro: contact_id obrigatório para qualificação."}
        return _wrap_result(
            qualify_contact_for_outreach(
                contact_id=req.contact_id,
                enrichment_confidence=req.confidence,
                divergence_whatsapp=bool(req.divergence_whatsapp),
                divergence_email=bool(req.divergence_email),
                divergence_company_or_cnpj=bool(req.divergence_company_or_cnpj),
                attempts_without_response=req.attempts_without_response or 0,
                intent_signal=req.intent_signal,
            )
        )

    if req.operation == "create_personalized_outreach_draft":
        if not req.contact_id:
            return {"result": "Erro: contact_id obrigatório para criar draft."}
        return _wrap_result(
            create_personalized_outreach_draft(
                contact_id=req.contact_id,
                channel=req.channel or "whatsapp",
            )
        )

    if req.operation == "approve_first_touch":
        if not req.contact_id:
            return {"result": "Erro: contact_id obrigatório para aprovar primeiro contato."}
        if not req.approved_by:
            return {"result": "Erro: approved_by obrigatório para rastreabilidade."}
        result = approve_first_touch(
            contact_id=req.contact_id,
            approved_by=req.approved_by,
            draft_interaction_id=req.draft_interaction_id,
            channel=req.channel or "whatsapp",
        )
        _record_operation_audit(
            actor=actor,
            role=role,
            operation=req.operation,
            resource_id=req.contact_id,
            status="success" if not (isinstance(result, dict) and "error" in result) else "error",
            reason=_resolve_operation_reason(req),
            after_payload=result,
            error=result.get("error") if isinstance(result, dict) else None,
        )
        return _wrap_result(result)

    if req.operation == "send_whatsapp_outreach":
        if not req.contact_id:
            return {"result": "Erro: contact_id obrigatório para envio WhatsApp."}
        return _wrap_result(
            send_whatsapp_outreach(
                contact_id=req.contact_id,
                draft_interaction_id=req.draft_interaction_id,
                messages=req.messages,
                require_approved=True if req.require_approved is None else req.require_approved,
                content_summary=req.content_summary,
                incoming_text=req.incoming_text,
                simulate_read_delay=True if req.simulate_read_delay is None else req.simulate_read_delay,
                read_delay_ms=req.read_delay_ms,
            )
        )

    if req.operation == "schedule_contact_task":
        if not req.contact_id:
            return {"result": "Erro: contact_id obrigatório para agendamento."}
        if not req.due_at or not req.objective:
            return {"result": "Erro: due_at e objective são obrigatórios para agendamento."}
        return _wrap_result(
            schedule_contact_task(
                contact_id=req.contact_id,
                due_at=req.due_at,
                channel=req.channel or "whatsapp",
                objective=req.objective,
                owner=req.owner,
                priority=req.priority or "medium",
                sla_hours=req.sla_hours,
                sync_calendar=True if req.sync_calendar is None else req.sync_calendar,
                reminder_at=req.reminder_at,
            )
        )

    if req.operation == "log_conversation_event":
        if not req.contact_id:
            return {"result": "Erro: contact_id obrigatório para log de conversa."}
        if not req.direction or not req.content_summary:
            return {"result": "Erro: direction e content_summary são obrigatórios para log."}
        return _wrap_result(
            log_conversation_event(
                contact_id=req.contact_id,
                channel=req.channel or "whatsapp",
                direction=req.direction,
                content_summary=req.content_summary,
                outcome=req.outcome,
                intent=req.stage,
                metadata=req.metadata,
                draft_interaction_id=req.draft_interaction_id,
                stage_hops=req.stage_hops,
                sla_hours=req.sla_hours,
            )
        )

    if req.operation == "mark_no_interest":
        if not req.contact_id:
            return {"result": "Erro: contact_id obrigatório para marcar desinteresse."}
        result = mark_no_interest(
            contact_id=req.contact_id,
            reason=req.reason,
            draft_interaction_id=req.draft_interaction_id,
            metadata=req.metadata,
        )
        _record_operation_audit(
            actor=actor,
            role=role,
            operation=req.operation,
            resource_id=req.contact_id,
            status="success" if not (isinstance(result, dict) and "error" in result) else "error",
            reason=_resolve_operation_reason(req),
            after_payload=result,
            error=result.get("error") if isinstance(result, dict) else None,
        )
        return _wrap_result(result)

    if req.operation == "sync_calendar_links":
        return _wrap_result(
            sync_calendar_links(
                limit=req.limit or 20,
                status_filter=req.status_filter or "pending_or_failed",
                calendar_id=req.calendar_id,
            )
        )

    if req.operation == "send_daily_improvement_report":
        return _wrap_result(
            send_daily_improvement_report(
                force=bool(req.force),
                channel_id=req.report_channel_id,
                target=req.target,
            )
        )

    if req.operation == "buffer_incoming_messages":
        lead_id = req.lead_id or req.contact_id
        if not lead_id:
            return {"result": "Erro: lead_id (ou contact_id) obrigatório para buffer."}
        if not req.event_text:
            return {"result": "Erro: event_text obrigatório para buffer."}
        return _wrap_result(
            buffer_incoming_messages(
                lead_id=lead_id,
                event_text=req.event_text,
                channel=req.channel or "whatsapp",
                message_id=req.message_id,
                max_hold_ms=req.max_hold_ms or 20000,
                max_msgs=req.max_msgs or 6,
                max_chars=req.max_chars or 1000,
            )
        )

    if req.operation == "route_conversation_turn":
        payload = req.payload or {}
        if req.content_summary:
            payload.setdefault("text", req.content_summary)
        if req.system_event:
            payload["system_event"] = req.system_event
        if req.is_audio:
            payload["is_audio"] = True
        return _wrap_result(route_conversation_turn(payload))

    if req.operation == "transcribe_incoming_audio":
        if not req.message_id or not req.media_ref:
            return {"result": "Erro: message_id e media_ref obrigatórios para transcrição."}
        return _wrap_result(
            transcribe_incoming_audio(
                message_id=req.message_id,
                media_ref=req.media_ref,
                transcript_hint=req.transcript_hint,
            )
        )

    if req.operation == "evaluate_dormant_leads":
        return _wrap_result(
            evaluate_dormant_leads(
                ruleset=req.ruleset,
                limit=req.limit or 50,
            )
        )

    if req.operation == "start_feedback_review_session":
        if not req.batch_id:
            return {"result": "Erro: batch_id obrigatório para iniciar review."}
        return _wrap_result(
            start_feedback_review_session(
                batch_id=req.batch_id,
                stage=req.stage,
                city=req.city,
                client_type=req.client_type,
                thread_ref=req.thread_ref,
                metadata=req.metadata,
            )
        )

    if req.operation == "record_human_feedback":
        if not req.session_id:
            return {"result": "Erro: session_id obrigatório para registrar feedback."}
        if not req.feedback_text:
            return {"result": "Erro: feedback_text obrigatório para registrar feedback."}
        return _wrap_result(
            record_human_feedback(
                session_id=req.session_id,
                feedback_text=req.feedback_text,
                tags=req.tags,
                author=req.author or "sales_reviewer",
                metadata=req.metadata,
            )
        )

    if req.operation == "generate_strategy_update_proposal":
        if not req.session_id:
            return {"result": "Erro: session_id obrigatório para gerar proposta."}
        return _wrap_result(
            generate_strategy_update_proposal(
                session_id=req.session_id,
                proposed_by=req.proposed_by or "feedback-reviewer-agent",
                top_n=req.limit or 5,
            )
        )

    if req.operation == "approve_strategy_updates":
        if not req.proposal_batch_id:
            return {"result": "Erro: proposal_batch_id obrigatório para aprovação."}
        if not req.approver:
            return {"result": "Erro: approver obrigatório para aprovação."}
        result = approve_strategy_updates(
            proposal_batch_id=req.proposal_batch_id,
            approver=req.approver,
            decision_notes=req.decision_notes,
        )
        _record_operation_audit(
            actor=actor,
            role=role,
            operation=req.operation,
            resource_id=req.proposal_batch_id,
            status="success" if not (isinstance(result, dict) and "error" in result) else "error",
            reason=_resolve_operation_reason(req),
            after_payload=result,
            error=result.get("error") if isinstance(result, dict) else None,
        )
        return _wrap_result(result)

    if req.operation == "reject_strategy_updates":
        if not req.proposal_batch_id:
            return {"result": "Erro: proposal_batch_id obrigatório para rejeição."}
        if not req.reason:
            return {"result": "Erro: reason obrigatório para rejeição."}
        result = reject_strategy_updates(
            proposal_batch_id=req.proposal_batch_id,
            reason=req.reason,
        )
        _record_operation_audit(
            actor=actor,
            role=role,
            operation=req.operation,
            resource_id=req.proposal_batch_id,
            status="success" if not (isinstance(result, dict) and "error" in result) else "error",
            reason=_resolve_operation_reason(req),
            after_payload=result,
            error=result.get("error") if isinstance(result, dict) else None,
        )
        return _wrap_result(result)

    if req.operation == "process_inbound_message":
        if not req.lead_id:
            return {"result": "Erro: lead_id obrigatório para process_inbound_message."}
        if not req.event_text and not (req.is_audio and req.media_ref):
            return {"result": "Erro: event_text obrigatório (ou is_audio+media_ref para áudio)."}
        if crm_inbound_pipe is None:
            return {"result": "Erro: pipes.crm_inbound_pipe não disponível neste ambiente."}
        return _wrap_result(
            crm_inbound_pipe.run(
                lead_id=req.lead_id,
                event_text=req.event_text or "",
                channel=req.channel or "whatsapp",
                message_id=req.message_id,
                media_ref=req.media_ref,
                is_audio=bool(req.is_audio),
                max_hold_ms=req.max_hold_ms or 20000,
                max_msgs=req.max_msgs or 6,
                max_chars=req.max_chars or 1000,
            )
        )

    return {"result": "Operação não suportada."}


async def sse_event_generator(operation: str, params: dict) -> AsyncGenerator[str, None]:
    import asyncio

    try:
        yield f"data: {json.dumps({'status': 'started', 'operation': operation})}\n\n"
        for i in range(3):
            await asyncio.sleep(1)
            yield f"data: {json.dumps({'progress': (i + 1) * 33, 'msg': f'Etapa {i + 1}/3', 'operation': operation})}\n\n"
        result = f"Operação {operation} executada com params {params}"
        yield f"data: {json.dumps({'status': 'done', 'result': result})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'status': 'error', 'error': str(e)})}\n\n"


@app.post("/sse", dependencies=[Depends(verify_api_key)])
async def sse_crm(req: CRMRequest, request: Request):
    async def event_stream():
        async for event in sse_event_generator(req.operation, req.model_dump()):
            if await request.is_disconnected():
                break
            yield event

    return StreamingResponse(event_stream(), media_type="text/event-stream")


logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("mcp-crm")
if Server is not None:
    mcp_server = Server("mcp-crm")


def _tool_text(result: dict | list | str) -> str:
    return result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)


if Server is not None:

    @mcp_server.list_tools()
    async def list_tools():
        return [
        Tool(
            name="add_contact",
            description="Adiciona um novo contato ao CRM. Obrigatório: nome + ao menos um de: email, whatsapp ou telefone.",
            inputSchema={
                "type": "object",
                "properties": {
                    "nome": {"type": "string"},
                    "apelido": {"type": "string"},
                    "tipo": {"type": "string"},
                    "email": {"type": "string"},
                    "telefone": {"type": "string"},
                    "whatsapp": {"type": "string"},
                    "linkedin": {"type": "string"},
                    "instagram": {"type": "string"},
                    "empresa": {"type": "string"},
                    "cargo": {"type": "string"},
                    "setor": {"type": "string"},
                    "city": {"type": "string"},
                    "region": {"type": "string"},
                    "client_type": {"type": "string"},
                    "nota": {"type": "string"},
                    "cnpj": {"type": "string"},
                    "cnaes": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["nome"],
            },
        ),
        Tool(
            name="search_contact",
            description="Busca contatos no CRM por nome ou empresa.",
            inputSchema={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        ),
        Tool(
            name="update_contact",
            description="Atualiza campos de um contato existente. Notas são appendadas com timestamp.",
            inputSchema={
                "type": "object",
                "properties": {
                    "contact_id": {"type": "string"},
                    "pipeline_status": {"type": "string", "enum": ["lead", "qualificado", "interesse", "proposta", "fechado", "perdido"]},
                    "stage": {"type": "string"},
                    "icp_type": {"type": "string", "enum": ["A", "B", "Hesitante"]},
                    "persona_profile": {"type": "string"},
                    "pain_hypothesis": {"type": "string"},
                    "recent_signal": {"type": "string"},
                    "offer_fit": {"type": "string"},
                    "preferred_tone": {"type": "string"},
                    "best_contact_window": {"type": "string"},
                    "readiness_status": {"type": "string"},
                    "needs_human_review": {"type": "boolean"},
                    "do_not_contact": {"type": "boolean"},
                    "do_not_contact_reason": {"type": "string"},
                    "nota": {"type": "string"},
                    "whatsapp": {"type": "string"},
                    "email": {"type": "string"},
                    "empresa": {"type": "string"},
                    "cargo": {"type": "string"},
                    "tipo": {"type": "string"},
                    "city": {"type": "string"},
                    "region": {"type": "string"},
                    "client_type": {"type": "string"},
                    "inferred_city": {"type": "boolean"},
                    "inferred_region": {"type": "boolean"},
                    "inferred_client_type": {"type": "boolean"},
                },
                "required": ["contact_id"],
            },
        ),
        Tool(
            name="list_contacts_to_follow_up",
            description="Lista contatos elegíveis para abordagem proativa.",
            inputSchema={
                "type": "object",
                "properties": {
                    "hours_since_last_contact": {"type": "integer"},
                    "limit": {"type": "integer"},
                },
                "required": [],
            },
        ),
        Tool(
            name="verify_contact_data",
            description="Valida canais e sinais verificados do contato.",
            inputSchema={
                "type": "object",
                "properties": {"contact_id": {"type": "string"}},
                "required": ["contact_id"],
            },
        ),
        Tool(
            name="enrich_contact_data",
            description="Executa enriquecimento de dados e marca frescor por 7 dias.",
            inputSchema={
                "type": "object",
                "properties": {
                    "contact_id": {"type": "string"},
                    "mode": {"type": "string", "enum": ["deep", "light"]},
                    "source": {"type": "string"},
                    "confidence": {"type": "number"},
                    "evidence": {"type": "string"},
                    "divergence_whatsapp": {"type": "boolean"},
                    "divergence_email": {"type": "boolean"},
                    "divergence_company_or_cnpj": {"type": "boolean"},
                },
                "required": ["contact_id"],
            },
        ),
        Tool(
            name="qualify_contact_for_outreach",
            description="Calcula readiness_score, aplica penalidades e valida gate de 1º contato.",
            inputSchema={
                "type": "object",
                "properties": {
                    "contact_id": {"type": "string"},
                    "confidence": {"type": "number"},
                    "divergence_whatsapp": {"type": "boolean"},
                    "divergence_email": {"type": "boolean"},
                    "divergence_company_or_cnpj": {"type": "boolean"},
                    "attempts_without_response": {"type": "integer"},
                    "intent_signal": {"type": "integer"},
                },
                "required": ["contact_id"],
            },
        ),
        Tool(
            name="create_personalized_outreach_draft",
            description="Gera draft humanizado por estágio usando playbook e battlecards.",
            inputSchema={
                "type": "object",
                "properties": {
                    "contact_id": {"type": "string"},
                    "channel": {"type": "string", "enum": ["whatsapp", "email"]},
                },
                "required": ["contact_id"],
            },
        ),
        Tool(
            name="approve_first_touch",
            description="Aprova o 1º toque humano e registra auditoria de aprovação.",
            inputSchema={
                "type": "object",
                "properties": {
                    "contact_id": {"type": "string"},
                    "approved_by": {"type": "string"},
                    "draft_interaction_id": {"type": "string"},
                    "channel": {"type": "string", "enum": ["whatsapp", "email"]},
                },
                "required": ["contact_id", "approved_by"],
            },
        ),
        Tool(
            name="send_whatsapp_outreach",
            description="Envia mensagens WhatsApp com simulação de digitação humana (presence=composing + delay).",
            inputSchema={
                "type": "object",
                "properties": {
                    "contact_id": {"type": "string"},
                    "draft_interaction_id": {"type": "string"},
                    "messages": {"type": "array", "items": {"type": "string"}},
                    "require_approved": {"type": "boolean"},
                    "content_summary": {"type": "string"},
                    "incoming_text": {"type": "string"},
                    "simulate_read_delay": {"type": "boolean"},
                    "read_delay_ms": {"type": "integer"},
                },
                "required": ["contact_id"],
            },
        ),
        Tool(
            name="schedule_contact_task",
            description="Agenda próximo contato e cria vínculo de sync com Google Calendar.",
            inputSchema={
                "type": "object",
                "properties": {
                    "contact_id": {"type": "string"},
                    "due_at": {"type": "string", "description": "ISO datetime"},
                    "channel": {"type": "string"},
                    "objective": {"type": "string"},
                    "owner": {"type": "string"},
                    "priority": {"type": "string"},
                    "sla_hours": {"type": "integer"},
                    "sync_calendar": {"type": "boolean"},
                    "reminder_at": {"type": "string", "description": "ISO datetime"},
                },
                "required": ["contact_id", "due_at", "objective"],
            },
        ),
        Tool(
            name="log_conversation_event",
            description="Registra evento de conversa (inbound/outbound) e atualiza status de contato.",
            inputSchema={
                "type": "object",
                "properties": {
                    "contact_id": {"type": "string"},
                    "channel": {"type": "string"},
                    "direction": {"type": "string", "enum": ["inbound", "outbound", "internal"]},
                    "content_summary": {"type": "string"},
                    "outcome": {"type": "string"},
                    "stage": {"type": "string"},
                    "draft_interaction_id": {"type": "string"},
                    "stage_hops": {"type": "integer"},
                    "sla_hours": {"type": "integer"},
                    "metadata": {"type": "object"},
                },
                "required": ["contact_id", "direction", "content_summary"],
            },
        ),
        Tool(
            name="mark_no_interest",
            description="Marca desinteresse e bloqueia permanentemente novos contatos.",
            inputSchema={
                "type": "object",
                "properties": {
                    "contact_id": {"type": "string"},
                    "reason": {"type": "string"},
                    "draft_interaction_id": {"type": "string"},
                    "metadata": {"type": "object"},
                },
                "required": ["contact_id"],
            },
        ),
        Tool(
            name="sync_calendar_links",
            description="Sincroniza tarefas pendentes/falhas com Google Calendar.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Quantidade máxima de itens no batch."},
                    "status_filter": {
                        "type": "string",
                        "enum": ["pending_or_failed", "pending_sync", "failed_sync", "all"],
                    },
                    "calendar_id": {"type": "string", "description": "Google Calendar ID alvo (default: env GOOGLE_CALENDAR_ID ou primary)."},
                },
                "required": [],
            },
        ),
        Tool(
            name="send_daily_improvement_report",
            description="Gera e envia relatório de melhoria para o canal sales-bot-improvement (12:00/19:00 BRT).",
            inputSchema={
                "type": "object",
                "properties": {
                    "force": {"type": "boolean"},
                    "report_channel_id": {"type": "string"},
                    "target": {"type": "string", "description": "Ex: channel:sales-bot-improvement"},
                },
                "required": [],
            },
        ),
        Tool(
            name="buffer_incoming_messages",
            description="Agrupa mensagens inbound de um lead em buffer semântico antes do roteamento.",
            inputSchema={
                "type": "object",
                "properties": {
                    "lead_id": {"type": "string"},
                    "event_text": {"type": "string"},
                    "channel": {"type": "string"},
                    "message_id": {"type": "string"},
                    "max_hold_ms": {"type": "integer"},
                    "max_msgs": {"type": "integer"},
                    "max_chars": {"type": "integer"},
                },
                "required": ["lead_id", "event_text"],
            },
        ),
        Tool(
            name="route_conversation_turn",
            description="Classifica intent e seleciona especialista (router).",
            inputSchema={
                "type": "object",
                "properties": {
                    "payload": {"type": "object"},
                    "content_summary": {"type": "string"},
                    "system_event": {"type": "string"},
                    "is_audio": {"type": "boolean"},
                },
                "required": [],
            },
        ),
        Tool(
            name="transcribe_incoming_audio",
            description="Transcreve áudio inbound para texto de contexto.",
            inputSchema={
                "type": "object",
                "properties": {
                    "message_id": {"type": "string"},
                    "media_ref": {"type": "string"},
                    "transcript_hint": {"type": "string"},
                },
                "required": ["message_id", "media_ref"],
            },
        ),
        Tool(
            name="evaluate_dormant_leads",
            description="Avalia leads dormentes e injeta eventos timeout_24h/48h/72h.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ruleset": {"type": "object"},
                    "limit": {"type": "integer"},
                },
                "required": [],
            },
        ),
        Tool(
            name="start_feedback_review_session",
            description="Inicia sessão de review humano para um batch.",
            inputSchema={
                "type": "object",
                "properties": {
                    "batch_id": {"type": "string"},
                    "stage": {"type": "string"},
                    "city": {"type": "string"},
                    "client_type": {"type": "string"},
                    "thread_ref": {"type": "string"},
                    "metadata": {"type": "object"},
                },
                "required": ["batch_id"],
            },
        ),
        Tool(
            name="record_human_feedback",
            description="Registra feedback humano em sessão de review.",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "feedback_text": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "author": {"type": "string"},
                    "metadata": {"type": "object"},
                },
                "required": ["session_id", "feedback_text"],
            },
        ),
        Tool(
            name="generate_strategy_update_proposal",
            description="Gera proposta de ajustes de estratégia para aprovação humana.",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "proposed_by": {"type": "string"},
                    "limit": {"type": "integer", "description": "top_n"},
                },
                "required": ["session_id"],
            },
        ),
        Tool(
            name="approve_strategy_updates",
            description="Aprova proposta e aplica ajustes de estratégia.",
            inputSchema={
                "type": "object",
                "properties": {
                    "proposal_batch_id": {"type": "string"},
                    "approver": {"type": "string"},
                    "decision_notes": {"type": "string"},
                },
                "required": ["proposal_batch_id", "approver"],
            },
        ),
        Tool(
            name="reject_strategy_updates",
            description="Rejeita proposta de ajustes de estratégia.",
            inputSchema={
                "type": "object",
                "properties": {
                    "proposal_batch_id": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["proposal_batch_id", "reason"],
            },
        ),
        Tool(
            name="process_inbound_message",
            description=(
                "Processa uma mensagem inbound de WhatsApp: buffer → roteamento de intent → "
                "despacho para specialist → envio da resposta. "
                "Retorna {status, intent, specialist, messages}."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "lead_id": {"type": "string", "description": "UUID do contato no CRM."},
                    "event_text": {"type": "string", "description": "Texto da mensagem recebida."},
                    "channel": {"type": "string", "description": "Canal de comunicação (default: whatsapp)."},
                    "message_id": {"type": "string"},
                    "is_audio": {"type": "boolean", "description": "True se a mensagem é áudio."},
                    "media_ref": {"type": "string", "description": "URL ou ref do arquivo de áudio."},
                    "max_hold_ms": {"type": "integer"},
                },
                "required": ["lead_id"],
            },
        ),
    ]


    @mcp_server.call_tool()
    async def call_tool(name: str, arguments: dict):
        try:
            if name == "add_contact":
                contato_id = add_contato(
                nome=arguments["nome"],
                apelido=arguments.get("apelido"),
                tipo=arguments.get("tipo"),
                telefone=arguments.get("telefone"),
                whatsapp=arguments.get("whatsapp"),
                email=arguments.get("email"),
                linkedin=arguments.get("linkedin"),
                instagram=arguments.get("instagram"),
                empresa=arguments.get("empresa"),
                cargo=arguments.get("cargo"),
                setor=arguments.get("setor"),
                city=arguments.get("city"),
                region=arguments.get("region"),
                client_type=arguments.get("client_type"),
                cnpj=arguments.get("cnpj"),
                cnaes=arguments.get("cnaes"),
                notas=arguments.get("nota") or arguments.get("notas"),
            )
                return [TextContent(type="text", text=f"Contato adicionado com ID: {contato_id}")]

            if name == "search_contact":
                return [TextContent(type="text", text=_tool_text(search_contatos(arguments["query"])))]

            if name == "update_contact":
                result = update_contato(
                contact_id=arguments["contact_id"],
                pipeline_status=arguments.get("pipeline_status"),
                stage=arguments.get("stage"),
                icp_type=arguments.get("icp_type"),
                persona_profile=arguments.get("persona_profile"),
                pain_hypothesis=arguments.get("pain_hypothesis"),
                recent_signal=arguments.get("recent_signal"),
                offer_fit=arguments.get("offer_fit"),
                preferred_tone=arguments.get("preferred_tone"),
                best_contact_window=arguments.get("best_contact_window"),
                readiness_status=arguments.get("readiness_status"),
                needs_human_review=arguments.get("needs_human_review"),
                do_not_contact=arguments.get("do_not_contact"),
                do_not_contact_reason=arguments.get("do_not_contact_reason"),
                nota=arguments.get("nota"),
                whatsapp=arguments.get("whatsapp"),
                email=arguments.get("email"),
                empresa=arguments.get("empresa"),
                cargo=arguments.get("cargo"),
                tipo=arguments.get("tipo"),
                city=arguments.get("city"),
                region=arguments.get("region"),
                client_type=arguments.get("client_type"),
                inferred_city=arguments.get("inferred_city"),
                inferred_region=arguments.get("inferred_region"),
                inferred_client_type=arguments.get("inferred_client_type"),
            )
                return [TextContent(type="text", text=_tool_text(result))]

            if name == "list_contacts_to_follow_up":
                contacts = list_contacts_to_follow_up(
                hours_since_last_contact=arguments.get("hours_since_last_contact", 24),
                limit=arguments.get("limit", 10),
            )
                return [TextContent(type="text", text=_tool_text(contacts))]

            if name == "verify_contact_data":
                return [TextContent(type="text", text=_tool_text(verify_contact_data(arguments["contact_id"])))]

            if name == "enrich_contact_data":
                result = enrich_contact_data(
                contact_id=arguments["contact_id"],
                mode=arguments.get("mode", "deep"),
                source=arguments.get("source"),
                confidence=arguments.get("confidence", 0.8),
                evidence=arguments.get("evidence"),
                divergence_whatsapp=bool(arguments.get("divergence_whatsapp", False)),
                divergence_email=bool(arguments.get("divergence_email", False)),
                divergence_company_or_cnpj=bool(arguments.get("divergence_company_or_cnpj", False)),
            )
                return [TextContent(type="text", text=_tool_text(result))]

            if name == "qualify_contact_for_outreach":
                result = qualify_contact_for_outreach(
                contact_id=arguments["contact_id"],
                enrichment_confidence=arguments.get("confidence"),
                divergence_whatsapp=bool(arguments.get("divergence_whatsapp", False)),
                divergence_email=bool(arguments.get("divergence_email", False)),
                divergence_company_or_cnpj=bool(arguments.get("divergence_company_or_cnpj", False)),
                attempts_without_response=arguments.get("attempts_without_response", 0),
                intent_signal=arguments.get("intent_signal"),
            )
                return [TextContent(type="text", text=_tool_text(result))]

            if name == "create_personalized_outreach_draft":
                result = create_personalized_outreach_draft(
                contact_id=arguments["contact_id"],
                channel=arguments.get("channel", "whatsapp"),
            )
                return [TextContent(type="text", text=_tool_text(result))]

            if name == "approve_first_touch":
                result = approve_first_touch(
                contact_id=arguments["contact_id"],
                approved_by=arguments["approved_by"],
                draft_interaction_id=arguments.get("draft_interaction_id"),
                channel=arguments.get("channel", "whatsapp"),
            )
                return [TextContent(type="text", text=_tool_text(result))]

            if name == "send_whatsapp_outreach":
                result = send_whatsapp_outreach(
                contact_id=arguments["contact_id"],
                draft_interaction_id=arguments.get("draft_interaction_id"),
                messages=arguments.get("messages"),
                require_approved=arguments.get("require_approved", True),
                content_summary=arguments.get("content_summary"),
                incoming_text=arguments.get("incoming_text"),
                simulate_read_delay=arguments.get("simulate_read_delay", True),
                read_delay_ms=arguments.get("read_delay_ms"),
            )
                return [TextContent(type="text", text=_tool_text(result))]

            if name == "schedule_contact_task":
                result = schedule_contact_task(
                contact_id=arguments["contact_id"],
                due_at=arguments["due_at"],
                channel=arguments.get("channel", "whatsapp"),
                objective=arguments["objective"],
                owner=arguments.get("owner"),
                priority=arguments.get("priority", "medium"),
                sla_hours=arguments.get("sla_hours", 24),
                sync_calendar=arguments.get("sync_calendar", True),
                reminder_at=arguments.get("reminder_at"),
            )
                return [TextContent(type="text", text=_tool_text(result))]

            if name == "log_conversation_event":
                result = log_conversation_event(
                contact_id=arguments["contact_id"],
                channel=arguments.get("channel", "whatsapp"),
                direction=arguments["direction"],
                content_summary=arguments["content_summary"],
                outcome=arguments.get("outcome"),
                intent=arguments.get("stage"),
                metadata=arguments.get("metadata"),
                draft_interaction_id=arguments.get("draft_interaction_id"),
                stage_hops=arguments.get("stage_hops"),
                sla_hours=arguments.get("sla_hours"),
            )
                return [TextContent(type="text", text=_tool_text(result))]

            if name == "mark_no_interest":
                result = mark_no_interest(
                    contact_id=arguments["contact_id"],
                    reason=arguments.get("reason"),
                    draft_interaction_id=arguments.get("draft_interaction_id"),
                    metadata=arguments.get("metadata"),
                )
                return [TextContent(type="text", text=_tool_text(result))]

            if name == "sync_calendar_links":
                result = sync_calendar_links(
                    limit=arguments.get("limit", 20),
                    status_filter=arguments.get("status_filter", "pending_or_failed"),
                    calendar_id=arguments.get("calendar_id"),
                )
                return [TextContent(type="text", text=_tool_text(result))]

            if name == "send_daily_improvement_report":
                result = send_daily_improvement_report(
                    force=bool(arguments.get("force", False)),
                    channel_id=arguments.get("report_channel_id"),
                    target=arguments.get("target"),
                )
                return [TextContent(type="text", text=_tool_text(result))]

            if name == "buffer_incoming_messages":
                result = buffer_incoming_messages(
                    lead_id=arguments["lead_id"],
                    event_text=arguments["event_text"],
                    channel=arguments.get("channel", "whatsapp"),
                    message_id=arguments.get("message_id"),
                    max_hold_ms=arguments.get("max_hold_ms", 20000),
                    max_msgs=arguments.get("max_msgs", 6),
                    max_chars=arguments.get("max_chars", 1000),
                )
                return [TextContent(type="text", text=_tool_text(result))]

            if name == "route_conversation_turn":
                payload = arguments.get("payload") or {}
                if arguments.get("content_summary"):
                    payload.setdefault("text", arguments.get("content_summary"))
                if arguments.get("system_event"):
                    payload["system_event"] = arguments.get("system_event")
                if arguments.get("is_audio"):
                    payload["is_audio"] = True
                result = route_conversation_turn(payload)
                return [TextContent(type="text", text=_tool_text(result))]

            if name == "transcribe_incoming_audio":
                result = transcribe_incoming_audio(
                    message_id=arguments["message_id"],
                    media_ref=arguments["media_ref"],
                    transcript_hint=arguments.get("transcript_hint"),
                )
                return [TextContent(type="text", text=_tool_text(result))]

            if name == "evaluate_dormant_leads":
                result = evaluate_dormant_leads(
                    ruleset=arguments.get("ruleset"),
                    limit=arguments.get("limit", 50),
                )
                return [TextContent(type="text", text=_tool_text(result))]

            if name == "start_feedback_review_session":
                result = start_feedback_review_session(
                    batch_id=arguments["batch_id"],
                    stage=arguments.get("stage"),
                    city=arguments.get("city"),
                    client_type=arguments.get("client_type"),
                    thread_ref=arguments.get("thread_ref"),
                    metadata=arguments.get("metadata"),
                )
                return [TextContent(type="text", text=_tool_text(result))]

            if name == "record_human_feedback":
                result = record_human_feedback(
                    session_id=arguments["session_id"],
                    feedback_text=arguments["feedback_text"],
                    tags=arguments.get("tags"),
                    author=arguments.get("author", "sales_reviewer"),
                    metadata=arguments.get("metadata"),
                )
                return [TextContent(type="text", text=_tool_text(result))]

            if name == "generate_strategy_update_proposal":
                result = generate_strategy_update_proposal(
                    session_id=arguments["session_id"],
                    proposed_by=arguments.get("proposed_by", "feedback-reviewer-agent"),
                    top_n=arguments.get("limit", 5),
                )
                return [TextContent(type="text", text=_tool_text(result))]

            if name == "approve_strategy_updates":
                result = approve_strategy_updates(
                    proposal_batch_id=arguments["proposal_batch_id"],
                    approver=arguments["approver"],
                    decision_notes=arguments.get("decision_notes"),
                )
                return [TextContent(type="text", text=_tool_text(result))]

            if name == "reject_strategy_updates":
                result = reject_strategy_updates(
                    proposal_batch_id=arguments["proposal_batch_id"],
                    reason=arguments["reason"],
                )
                return [TextContent(type="text", text=_tool_text(result))]

            if name == "process_inbound_message":
                if crm_inbound_pipe is None:
                    return [TextContent(type="text", text="Erro: pipes.crm_inbound_pipe não disponível.")]
                result = crm_inbound_pipe.run(
                    lead_id=arguments["lead_id"],
                    event_text=arguments.get("event_text", ""),
                    channel=arguments.get("channel", "whatsapp"),
                    message_id=arguments.get("message_id"),
                    media_ref=arguments.get("media_ref"),
                    is_audio=bool(arguments.get("is_audio", False)),
                    max_hold_ms=int(arguments.get("max_hold_ms", 20000)),
                )
                return [TextContent(type="text", text=_tool_text(result))]

            raise ValueError(f"Tool not found: {name}")
        except Exception as e:
            logger.error(f"Erro ao executar ferramenta {name}: {e}")
            return [TextContent(type="text", text=f"Erro interno: {str(e)}")]


    async def main_mcp():
        try:
            async with stdio_server() as (read_stream, write_stream):
                await mcp_server.run(read_stream, write_stream, mcp_server.create_initialization_options())
        except Exception as e:
            logger.error(f"Falha fatal no servidor MCP crm: {e}", exc_info=True)
            sys.exit(1)
else:  # pragma: no cover

    async def main_mcp():
        raise RuntimeError("Dependência 'mcp' não encontrada. Instale mcp[stdio] para uso via STDIO.")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main_mcp())
