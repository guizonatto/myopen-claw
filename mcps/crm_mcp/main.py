from __future__ import annotations

import json
import logging
import sys
from typing import AsyncGenerator, Literal, Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import text

try:
    from .auth import verify_api_key
    from .contatos import (
        add_contato,
        approve_first_touch,
        create_personalized_outreach_draft,
        enrich_contact_data,
        list_contacts_to_follow_up,
        log_conversation_event,
        mark_no_interest,
        qualify_contact_for_outreach,
        schedule_contact_task,
        search_contatos,
        send_daily_improvement_report,
        send_whatsapp_outreach,
        sync_calendar_links,
        update_contato,
        verify_contact_data,
    )
    from .db import get_session
except ImportError:  # pragma: no cover
    from auth import verify_api_key
    from contatos import (
        add_contato,
        approve_first_touch,
        create_personalized_outreach_draft,
        enrich_contact_data,
        list_contacts_to_follow_up,
        log_conversation_event,
        mark_no_interest,
        qualify_contact_for_outreach,
        schedule_contact_task,
        search_contatos,
        send_daily_improvement_report,
        send_whatsapp_outreach,
        sync_calendar_links,
        update_contato,
        verify_contact_data,
    )
    from db import get_session

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


def _wrap_result(result):
    if isinstance(result, dict) and "error" in result:
        return {"result": result["error"]}
    return {"result": result}


@app.post("/execute", dependencies=[Depends(verify_api_key)])
def execute_crm(req: CRMRequest):
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
        return _wrap_result(
            approve_first_touch(
                contact_id=req.contact_id,
                approved_by=req.approved_by,
                draft_interaction_id=req.draft_interaction_id,
                channel=req.channel or "whatsapp",
            )
        )

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
        return _wrap_result(
            mark_no_interest(
                contact_id=req.contact_id,
                reason=req.reason,
                draft_interaction_id=req.draft_interaction_id,
                metadata=req.metadata,
            )
        )

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
            description="Adiciona um novo contato ao CRM (email OU whatsapp OU telefone).",
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
                "anyOf": [{"required": ["email"]}, {"required": ["whatsapp"]}, {"required": ["telefone"]}],
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
