from __future__ import annotations

import json
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import or_

try:
    from .calendar_sync import sync_calendar_links as sync_calendar_links_worker
    from .conversation_engine import build_personalized_draft
    from .db import get_session
    from .improvement_report import send_daily_improvement_report as send_daily_improvement_report_impl
    from .message_strategy import (
        apply_inference_to_contact,
        build_daily_improvement_snapshot,
        record_strategy_outcome,
        resolve_contact_dimensions,
        resolve_sla_outcome,
        select_message_strategy,
        update_strategy_ranking,
    )
    from .models import (
        CalendarLink,
        ContactEnrichmentRun,
        FeedbackReviewEntry,
        FeedbackReviewSession,
        ContactInteraction,
        IncomingMessageBuffer,
        ContactTask,
        Contato,
        StrategyUpdateProposal,
        MessageStrategyRanking,
    )
    from .readiness import READINESS_STATES, ReadinessInput, calculate_readiness, can_transition
    from .whatsapp_sender import human_read_delay_ms, send_whatsapp_messages
except ImportError:  # pragma: no cover
    from calendar_sync import sync_calendar_links as sync_calendar_links_worker
    from conversation_engine import build_personalized_draft
    from db import get_session
    from improvement_report import send_daily_improvement_report as send_daily_improvement_report_impl
    from message_strategy import (
        apply_inference_to_contact,
        build_daily_improvement_snapshot,
        record_strategy_outcome,
        resolve_contact_dimensions,
        resolve_sla_outcome,
        select_message_strategy,
        update_strategy_ranking,
    )
    from models import (
        CalendarLink,
        ContactEnrichmentRun,
        ContactInteraction,
        ContactTask,
        Contato,
        FeedbackReviewEntry,
        FeedbackReviewSession,
        IncomingMessageBuffer,
        MessageStrategyRanking,
        StrategyUpdateProposal,
    )
    from readiness import READINESS_STATES, ReadinessInput, calculate_readiness, can_transition
    from whatsapp_sender import human_read_delay_ms, send_whatsapp_messages


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\+?\d{10,15}$")
VALID_PIPELINE = {"lead", "qualificado", "interesse", "proposta", "fechado", "perdido", "follow_up_pause"}
BOT_ROUTER_KEYWORDS = (
    "bloco",
    "unidade",
    "apartamento",
    "apto",
    "torre",
    "portaria",
    "identifique",
    "digite",
)

PROACTIVE_TIMEOUTS = (
    ("timeout_72h", 72),
    ("timeout_48h", 48),
    ("timeout_24h", 24),
)

INTENT_TO_SPECIALIST = {
    "greeting": "zind-crm-cold-contact",
    "proactive_follow_up": "zind-crm-cold-contact",
    "identity_check": "zind-crm-qualifier",
    "interest_uncertain": "zind-crm-qualifier",
    "objection_price": "zind-crm-qualifier",
    "objection_time": "zind-crm-qualifier",
    "objection_trust": "zind-crm-qualifier",
    "objection_already_has_solution": "zind-crm-qualifier",
    "objection_competitor": "zind-crm-qualifier",
    "request_proof": "zind-crm-qualifier",
    "bot_gatekeeper": "zind-crm-qualifier",
    "out_of_scope_junk": "zind-crm-qualifier",
    "interest_positive": "zind-crm-closer",
    "request_demo_or_meeting": "zind-crm-closer",
    "request_human": "zind-crm-handover",
    "no_interest": "zind-crm-handover",
    "escalate_frustration": "zind-crm-handover",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_digits(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\D+", "", value)


def _is_valid_email(value: str | None) -> bool:
    return bool(value and EMAIL_RE.match(value.strip()))


def _is_valid_phone(value: str | None) -> bool:
    digits = _normalize_digits(value)
    return bool(PHONE_RE.match(digits))


def _is_valid_cnpj(value: str | None) -> bool:
    return len(_normalize_digits(value)) == 14


def _count_verified_signals(contato: Contato) -> int:
    signals = [
        _is_valid_email(contato.email),
        _is_valid_phone(contato.whatsapp),
        _is_valid_phone(contato.telefone),
        bool((contato.empresa or "").strip() or _is_valid_cnpj(contato.cnpj)),
    ]
    return sum(1 for item in signals if item)


def _parse_iso_datetime(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo:
            return value
        return value.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo:
        return parsed
    return parsed.replace(tzinfo=timezone.utc)


def _try_transition(contato: Contato, target: str, *, force: bool = False) -> bool:
    if target not in READINESS_STATES:
        return False
    if force or target == "blocked":
        contato.readiness_status = target
        return True
    if can_transition(contato.readiness_status, target):
        contato.readiness_status = target
        return True
    return False


def _last_enrichment_confidence(session, contact_id: str, default: float) -> float:
    latest = (
        session.query(ContactEnrichmentRun)
        .filter(ContactEnrichmentRun.contato_id == contact_id)
        .order_by(ContactEnrichmentRun.created_at.desc())
        .first()
    )
    if latest and latest.confidence is not None:
        return float(latest.confidence)
    return default


def _intent_score(stage: str | None) -> int:
    stage_value = (stage or "").strip().lower()
    if stage_value in {"aceite", "proposta", "follow_up_quente"}:
        return 9
    if stage_value in {"curiosidade_ativa", "interesse"}:
        return 7
    if stage_value in {"caos_operacional", "objecao_preco"}:
        return 6
    return 5


def _serialize_json(value: dict | None) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def _deserialize_json(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _resolve_sla_hours(session, contato_id: str, fallback: int = 24) -> int:
    task = (
        session.query(ContactTask)
        .filter(ContactTask.contato_id == contato_id)
        .order_by(ContactTask.created_at.desc())
        .first()
    )
    if task and task.sla_hours and task.sla_hours > 0:
        return int(task.sla_hours)
    return fallback


def _resolve_last_outbound_at(session, contato_id: str) -> datetime | None:
    interaction = (
        session.query(ContactInteraction)
        .filter(
            ContactInteraction.contato_id == contato_id,
            ContactInteraction.direction == "outbound",
        )
        .order_by(ContactInteraction.created_at.desc())
        .first()
    )
    if not interaction:
        return None
    if interaction.sent_at:
        return interaction.sent_at
    return interaction.created_at


def _resolve_last_inbound_interaction(session, contato_id: str) -> ContactInteraction | None:
    return (
        session.query(ContactInteraction)
        .filter(
            ContactInteraction.contato_id == contato_id,
            ContactInteraction.direction == "inbound",
        )
        .order_by(ContactInteraction.created_at.desc())
        .first()
    )


def _is_bot_router_message(text: str | None) -> bool:
    normalized = (text or "").strip().lower()
    if not normalized:
        return False
    return any(keyword in normalized for keyword in BOT_ROUTER_KEYWORDS)


def _is_complete_message(text: str) -> tuple[bool, str]:
    normalized = (text or "").strip().lower()
    if not normalized:
        return False, "empty"
    if len(normalized) >= 120:
        return True, "semantic_complete_long"
    if "?" in normalized:
        return True, "semantic_complete_question"
    completion_markers = (
        "pode",
        "consigo",
        "valor",
        "preco",
        "preço",
        "agendar",
        "reuniao",
        "reunião",
        "interesse",
        "nao tenho interesse",
        "não tenho interesse",
    )
    if any(marker in normalized for marker in completion_markers):
        return True, "semantic_complete_marker"
    return False, "incomplete"


def _detect_intent(text: str, *, system_event: str | None = None) -> tuple[str, float]:
    normalized = (text or "").strip().lower()
    if system_event in {"timeout_24h", "timeout_48h", "timeout_72h"}:
        return "proactive_follow_up", 0.95
    if not normalized:
        return "out_of_scope_junk", 0.2
    if _is_bot_router_message(normalized):
        return "bot_gatekeeper", 0.92
    # escalate — explicit frustration signals
    if any(word in normalized for word in (
        "palhaçada", "absurdo", "ridículo", "ridiculo",
        "lixo", "merda", "idiota", "porra", "puta",
        "frustrad", "raiva", "indignado",
    )):
        return "escalate_frustration", 0.96
    # no_interest — opt-out / removal requests
    if any(phrase in normalized for phrase in (
        "nao tenho interesse", "não tenho interesse",
        "sem interesse", "nao quero", "não quero",
        "para de me", "pare de me", "me remove", "remova",
        "cancela", "cancelar", "descadastra",
    )):
        return "no_interest", 0.98
    # request_human — wants a person
    if any(word in normalized for word in (
        "humano", "atendente", "pessoa real", "alguem real", "alguém real",
        "falar com alguem", "falar com alguém", "gerente", "responsavel", "responsável",
    )):
        return "request_human", 0.9
    # demo / meeting
    if any(word in normalized for word in (
        "demo", "demonstra", "agenda", "agendar",
        "reuniao", "reunião", "call", "conversa rapida", "conversa rápida",
    )):
        return "request_demo_or_meeting", 0.92
    # proof / material
    if any(word in normalized for word in ("site", "video", "vídeo", "artigo", "case", "prova", "exemplo")):
        return "request_proof", 0.84
    # competitor / already has solution
    if any(phrase in normalized for phrase in (
        "concorrente", "ja uso", "já uso", "outra plataforma",
        "outro sistema", "ja temos", "já temos", "ja usamos", "já usamos",
        "ja tenho", "já tenho", "solucao parecida", "solução parecida",
        "fornecedor", "contrato",
    )):
        if any(word in normalized for word in ("concorrente", "fornecedor", "contrato", "outra", "outro")):
            return "objection_competitor", 0.88
        return "objection_already_has_solution", 0.84
    # price objection
    if any(word in normalized for word in ("caro", "preco", "preço", "valor", "custo", "investimento")):
        return "objection_price", 0.86
    # time objection
    if any(word in normalized for word in ("sem tempo", "tenho tempo", "depois", "mais tarde", "agora nao", "agora não", "nao tenho tempo", "não tenho tempo")):
        return "objection_time", 0.8
    # trust objection
    if any(word in normalized for word in ("funciona", "confiavel", "confiável", "golpe", "fraude", "suspeito")):
        return "objection_trust", 0.8
    # greeting
    if any(word in normalized for word in ("oi", "ola", "olá", "bom dia", "boa tarde", "boa noite")) and len(normalized) <= 30:
        return "greeting", 0.72
    # identity check (sindico, role, name)
    if any(word in normalized for word in ("sindico", "síndico", "ainda atende", "quem é você", "quem e voce")):
        return "identity_check", 0.74
    # positive interest
    if any(phrase in normalized for phrase in (
        "tenho interesse", "quero saber", "gostei",
        "faz sentido", "faz sentindo", "pode ser",
        "pode avançar", "pode avancar", "quero avançar",
    )):
        return "interest_positive", 0.77
    if normalized in ("sim", "claro", "ok", "okay", "top", "show"):
        return "interest_positive", 0.7
    # uncertain
    if any(word in normalized for word in ("talvez", "não sei", "nao sei", "como funciona", "me explica")):
        return "interest_uncertain", 0.68
    if len(normalized) <= 3:
        return "out_of_scope_junk", 0.45
    return "interest_uncertain", 0.55


def _policy_flags_for_intent(intent: str, *, is_audio: bool = False) -> list[str]:
    flags: list[str] = []
    if intent == "proactive_follow_up":
        flags.append("soft_ping")
    if intent == "escalate_frustration":
        flags.append("urgent_handover")
    if intent == "request_human":
        flags.append("handover_requested")
    if is_audio:
        flags.append("audio_origin_informal_ok")
    if intent == "no_interest":
        flags.append("block_and_stop")
    return flags


def _has_outbound_conversation(session, contato_id: str) -> bool:
    row = (
        session.query(ContactInteraction)
        .filter(
            ContactInteraction.contato_id == contato_id,
            ContactInteraction.direction == "outbound",
            ContactInteraction.kind == "conversation",
        )
        .first()
    )
    return row is not None


def _resolve_archetype_hint_for_outreach(session, contato: Contato, *, channel: str) -> str | None:
    if channel != "whatsapp":
        return None

    latest_inbound = _resolve_last_inbound_interaction(session, str(contato.id))
    if latest_inbound and _is_bot_router_message(latest_inbound.content_summary):
        return "bot_router_vendor_pitch"

    if (contato.pipeline_status or "").strip().lower() == "lead" and not _has_outbound_conversation(session, str(contato.id)):
        return "human_direct_probe_3step"

    return None


def _resolve_messages_for_whatsapp_send(
    session,
    contato: Contato,
    *,
    explicit_messages: list[str] | None,
    draft_row: ContactInteraction | None,
) -> list[str]:
    if explicit_messages:
        return [msg.strip() for msg in explicit_messages if (msg or "").strip()]

    if draft_row:
        metadata = _deserialize_json(draft_row.metadata_json)
        messages = metadata.get("messages")
        if isinstance(messages, list):
            clean = [str(msg).strip() for msg in messages if str(msg).strip()]
            if clean:
                return clean
        if draft_row.draft_text and draft_row.draft_text.strip():
            return [draft_row.draft_text.strip()]

    archetype_hint = _resolve_archetype_hint_for_outreach(session, contato, channel="whatsapp")
    strategy = select_message_strategy(
        session,
        contato,
        channel="whatsapp",
        archetype_hint=archetype_hint,
    )
    payload = build_personalized_draft(contato, channel="whatsapp", strategy=strategy)
    auto_messages = payload.get("messages") or [payload.get("draft", "")]
    return [str(msg).strip() for msg in auto_messages if str(msg).strip()]


def add_contato(
    nome: str,
    apelido: str | None = None,
    tipo: str | None = None,
    aniversario: date | None = None,
    telefone: str | None = None,
    whatsapp: str | None = None,
    email: str | None = None,
    linkedin: str | None = None,
    instagram: str | None = None,
    empresa: str | None = None,
    cargo: str | None = None,
    setor: str | None = None,
    city: str | None = None,
    region: str | None = None,
    client_type: str | None = None,
    cnpj: str | None = None,
    cnaes: list | None = None,
    notas: str | None = None,
) -> str:
    with get_session() as session:
        contato = Contato(
            nome=nome,
            apelido=apelido,
            tipo=tipo,
            aniversario=aniversario,
            telefone=telefone,
            whatsapp=whatsapp,
            email=email,
            linkedin=linkedin,
            instagram=instagram,
            empresa=empresa,
            cargo=cargo,
            setor=setor,
            city=city,
            region=region,
            client_type=client_type,
            cnpj=cnpj,
            cnaes=cnaes,
            notas=notas,
            readiness_status="ingested",
            needs_human_review=True,
            do_not_contact=False,
        )
        contato.verified_signals_count = _count_verified_signals(contato)
        session.add(contato)
        session.flush()
        return str(contato.id)


def update_contato(
    contact_id: str,
    apelido: str | None = None,
    tipo: str | None = None,
    whatsapp: str | None = None,
    email: str | None = None,
    telefone: str | None = None,
    linkedin: str | None = None,
    instagram: str | None = None,
    empresa: str | None = None,
    cargo: str | None = None,
    setor: str | None = None,
    city: str | None = None,
    region: str | None = None,
    client_type: str | None = None,
    inferred_city: bool | None = None,
    inferred_region: bool | None = None,
    inferred_client_type: bool | None = None,
    pipeline_status: str | None = None,
    stage: str | None = None,
    icp_type: str | None = None,
    persona_profile: str | None = None,
    pain_hypothesis: str | None = None,
    recent_signal: str | None = None,
    offer_fit: str | None = None,
    preferred_tone: str | None = None,
    best_contact_window: str | None = None,
    readiness_status: str | None = None,
    needs_human_review: bool | None = None,
    do_not_contact: bool | None = None,
    do_not_contact_reason: str | None = None,
    nota: str | None = None,
) -> dict:
    """Atualiza campos de um contato. Notas são appendadas com timestamp, nunca sobrescritas."""
    with get_session() as session:
        contato = session.query(Contato).filter(Contato.id == contact_id, Contato.ativo == True).first()  # noqa: E712
        if not contato:
            return {"error": f"Contato {contact_id} não encontrado."}

        if pipeline_status and pipeline_status not in VALID_PIPELINE:
            return {"error": f"pipeline_status inválido. Use: {', '.join(sorted(VALID_PIPELINE))}"}
        if readiness_status and readiness_status not in READINESS_STATES:
            return {"error": f"readiness_status inválido. Use: {', '.join(sorted(READINESS_STATES))}"}
        if readiness_status and not _try_transition(contato, readiness_status):
            return {"error": f"Transição de readiness_status inválida: {contato.readiness_status} -> {readiness_status}"}

        updateable = {
            "apelido": apelido,
            "tipo": tipo,
            "whatsapp": whatsapp,
            "email": email,
            "telefone": telefone,
            "linkedin": linkedin,
            "instagram": instagram,
            "empresa": empresa,
            "cargo": cargo,
            "setor": setor,
            "city": city,
            "region": region,
            "client_type": client_type,
            "pipeline_status": pipeline_status,
            "stage": stage,
            "icp_type": icp_type,
            "persona_profile": persona_profile,
            "pain_hypothesis": pain_hypothesis,
            "recent_signal": recent_signal,
            "offer_fit": offer_fit,
            "preferred_tone": preferred_tone,
            "best_contact_window": best_contact_window,
        }
        for field, value in updateable.items():
            if value is not None:
                setattr(contato, field, value)

        if inferred_city is not None:
            contato.inferred_city = inferred_city
        if inferred_region is not None:
            contato.inferred_region = inferred_region
        if inferred_client_type is not None:
            contato.inferred_client_type = inferred_client_type

        if needs_human_review is not None:
            contato.needs_human_review = needs_human_review

        if do_not_contact is not None:
            contato.do_not_contact = do_not_contact
            if do_not_contact:
                contato.do_not_contact_reason = do_not_contact_reason or contato.do_not_contact_reason or "manual_block"
                contato.do_not_contact_at = _utcnow()
                _try_transition(contato, "blocked", force=True)
                contato.pipeline_status = "perdido"
            elif do_not_contact is False:
                contato.do_not_contact_reason = None
                contato.do_not_contact_at = None

        if do_not_contact_reason and not contato.do_not_contact:
            contato.do_not_contact_reason = do_not_contact_reason

        if nota:
            ts = _utcnow().strftime("%Y-%m-%d %H:%M")
            existing = contato.notas or ""
            contato.notas = f"{existing}\n{ts}: {nota}".strip()

        contato.verified_signals_count = _count_verified_signals(contato)
        contato.ultimo_contato = _utcnow()
        contato.updated_at = _utcnow()
        session.flush()
        return contato.to_dict()


def verify_contact_data(contact_id: str) -> dict:
    with get_session() as session:
        contato = session.query(Contato).filter(Contato.id == contact_id, Contato.ativo == True).first()  # noqa: E712
        if not contato:
            return {"error": f"Contato {contact_id} não encontrado."}

        verification = {
            "email_valid": _is_valid_email(contato.email),
            "whatsapp_valid": _is_valid_phone(contato.whatsapp),
            "phone_valid": _is_valid_phone(contato.telefone),
            "company_identity_valid": bool((contato.empresa or "").strip() or _is_valid_cnpj(contato.cnpj)),
        }
        contato.verified_signals_count = sum(1 for ok in verification.values() if ok)
        target = "verified" if contato.verified_signals_count > 0 else "ingested"
        _try_transition(contato, target, force=contato.readiness_status is None)
        contato.updated_at = _utcnow()
        session.flush()
        return {
            "contact": contato.to_dict(),
            "verification": verification,
            "verified_signals_count": contato.verified_signals_count,
        }


def enrich_contact_data(
    contact_id: str,
    mode: str = "deep",
    source: str | None = None,
    confidence: float = 0.8,
    evidence: str | None = None,
    divergence_whatsapp: bool = False,
    divergence_email: bool = False,
    divergence_company_or_cnpj: bool = False,
) -> dict:
    with get_session() as session:
        contato = session.query(Contato).filter(Contato.id == contact_id, Contato.ativo == True).first()  # noqa: E712
        if not contato:
            return {"error": f"Contato {contact_id} não encontrado."}

        now = _utcnow()
        if mode == "deep":
            if not contato.persona_profile:
                contacto_context = [contato.cargo, contato.setor, contato.tipo]
                contato.persona_profile = " | ".join([x for x in contacto_context if x]) or "perfil_b2b_padrao"
            if not contato.offer_fit:
                contato.offer_fit = "otimizar operacao comercial e follow-up"
            if not contato.preferred_tone:
                contato.preferred_tone = "humano_profissional"
            if not contato.best_contact_window:
                contato.best_contact_window = "09:00-11:00"

            dimensions = resolve_contact_dimensions(contato, channel="whatsapp")
            apply_inference_to_contact(contato, dimensions)

        contato.last_enriched_at = now
        contato.fresh_until = now + timedelta(days=7)
        _try_transition(contato, "enriched", force=contato.readiness_status in {None, "ingested"})
        contato.updated_at = now

        run = ContactEnrichmentRun(
            contato_id=contato.id,
            mode=mode,
            source=source or "manual",
            confidence=confidence,
            evidence=evidence,
            divergence_whatsapp=divergence_whatsapp,
            divergence_email=divergence_email,
            divergence_company_or_cnpj=divergence_company_or_cnpj,
            notes=f"enrichment_mode={mode}",
        )
        session.add(run)
        session.flush()
        return {"contact": contato.to_dict(), "enrichment_run": run.to_dict()}


def qualify_contact_for_outreach(
    contact_id: str,
    enrichment_confidence: float | None = None,
    divergence_whatsapp: bool = False,
    divergence_email: bool = False,
    divergence_company_or_cnpj: bool = False,
    attempts_without_response: int = 0,
    intent_signal: int | None = None,
) -> dict:
    with get_session() as session:
        contato = session.query(Contato).filter(Contato.id == contact_id, Contato.ativo == True).first()  # noqa: E712
        if not contato:
            return {"error": f"Contato {contact_id} não encontrado."}

        now = _utcnow()
        if contato.last_enriched_at:
            fresh_days = (now - contato.last_enriched_at).days
        else:
            fresh_days = None

        confidence = (
            float(enrichment_confidence)
            if enrichment_confidence is not None
            else _last_enrichment_confidence(session, contact_id, default=0.8)
        )
        payload = ReadinessInput(
            has_whatsapp=_is_valid_phone(contato.whatsapp),
            has_email=_is_valid_email(contato.email),
            has_phone=_is_valid_phone(contato.telefone),
            verified_signals_count=max(contato.verified_signals_count or 0, _count_verified_signals(contato)),
            icp_type=contato.icp_type,
            pain_hypothesis=contato.pain_hypothesis,
            fresh_days=fresh_days,
            intent_signal=intent_signal if intent_signal is not None else _intent_score(contato.stage),
            enrichment_confidence=confidence,
            divergence_whatsapp=divergence_whatsapp,
            divergence_email=divergence_email,
            divergence_company_or_cnpj=divergence_company_or_cnpj,
            attempts_without_response=attempts_without_response,
            do_not_contact=bool(contato.do_not_contact),
            has_best_contact_window=bool((contato.best_contact_window or "").strip()),
        )
        result = calculate_readiness(payload)

        contato.readiness_score = result.readiness_score
        contato.verified_signals_count = payload.verified_signals_count
        contato.needs_human_review = True

        if result.hard_block_reason:
            _try_transition(contato, "blocked", force=True)
        elif result.gate_passed:
            _try_transition(contato, "qualified", force=contato.readiness_status is None)
        else:
            _try_transition(contato, "enriched", force=contato.readiness_status is None)

        if result.suggested_pipeline_status == "perdido":
            contato.pipeline_status = "perdido"

        contato.updated_at = now
        session.flush()
        return {
            "contact": contato.to_dict(),
            "score": {
                "positive_score": result.positive_score,
                "penalty_score": result.penalty_score,
                "readiness_score": result.readiness_score,
                "positives": result.positives,
                "penalties": result.penalties,
            },
            "gate_passed": result.gate_passed,
            "hard_block_reason": result.hard_block_reason,
            "suggested_pipeline_status": result.suggested_pipeline_status,
        }


def create_personalized_outreach_draft(contact_id: str, channel: str = "whatsapp") -> dict:
    with get_session() as session:
        contato = session.query(Contato).filter(Contato.id == contact_id, Contato.ativo == True).first()  # noqa: E712
        if not contato:
            return {"error": f"Contato {contact_id} não encontrado."}
        if contato.do_not_contact:
            return {"error": "Contato bloqueado por do_not_contact."}
        if contato.pipeline_status in {"fechado", "perdido"}:
            return {"error": f"Contato em status {contato.pipeline_status}. Não gerar novo 1º contato."}
        if not contato.readiness_score or contato.readiness_score < 70:
            return {"error": "Contato ainda não elegível: readiness_score < 70."}
        if (contato.verified_signals_count or 0) < 2:
            return {"error": "Contato ainda não elegível: verified_signals_count < 2."}
        if not contato.fresh_until or contato.fresh_until < _utcnow():
            return {"error": "Contato ainda não elegível: dados sem frescor válido."}
        if channel == "whatsapp" and not _is_valid_phone(contato.whatsapp):
            return {"error": "Canal WhatsApp indisponível para este contato."}
        if channel == "email" and not _is_valid_email(contato.email):
            return {"error": "Canal email indisponível para este contato."}

        archetype_hint = _resolve_archetype_hint_for_outreach(session, contato, channel=channel)
        strategy = select_message_strategy(
            session,
            contato,
            channel=channel,
            archetype_hint=archetype_hint,
        )
        apply_inference_to_contact(contato, strategy)
        payload = build_personalized_draft(contato, channel=channel, strategy=strategy)
        draft = payload["draft"]
        messages = payload.get("messages", [draft])

        metadata = {
            "checks": payload.get("checks"),
            "stage": contato.pipeline_status,
            "strategy_key": payload.get("strategy_key"),
            "message_archetype": payload.get("message_archetype"),
            "confidence": payload.get("confidence"),
            "retrieval_level": payload.get("retrieval_level"),
            "messages": messages,
            "split_applied": payload.get("split_applied", False),
            "client_type": strategy.get("client_type"),
            "city": strategy.get("city"),
            "region": strategy.get("region"),
        }
        interaction = ContactInteraction(
            contato_id=contato.id,
            channel=channel,
            direction="outbound",
            kind="draft",
            content_summary="Draft personalizado gerado para aprovação.",
            draft_text=draft,
            metadata_json=_serialize_json(metadata),
        )
        session.add(interaction)
        _try_transition(contato, "awaiting_approval", force=contato.readiness_status is None)
        contato.needs_human_review = True
        contato.updated_at = _utcnow()
        session.flush()
        return {
            "draft_id": str(interaction.id),
            "contact_id": contact_id,
            "channel": channel,
            "draft": draft,
            "messages": messages,
            "split_applied": payload.get("split_applied", False),
            "strategy_key": payload.get("strategy_key"),
            "message_archetype": payload.get("message_archetype"),
            "confidence": payload.get("confidence", 0.0),
            "checks": payload.get("checks", {}),
            "requires_approval": True,
        }


def approve_first_touch(
    contact_id: str,
    approved_by: str,
    draft_interaction_id: str | None = None,
    channel: str = "whatsapp",
) -> dict:
    with get_session() as session:
        contato = session.query(Contato).filter(Contato.id == contact_id, Contato.ativo == True).first()  # noqa: E712
        if not contato:
            return {"error": f"Contato {contact_id} não encontrado."}
        if contato.do_not_contact:
            return {"error": "Contato bloqueado por do_not_contact."}

        draft_text = None
        approval_metadata: dict[str, Any] = {}
        if draft_interaction_id:
            draft_row = (
                session.query(ContactInteraction)
                .filter(
                    ContactInteraction.id == draft_interaction_id,
                    ContactInteraction.contato_id == contact_id,
                    ContactInteraction.kind == "draft",
                )
                .first()
            )
            if not draft_row:
                return {"error": f"Draft {draft_interaction_id} não encontrado para o contato."}
            draft_text = draft_row.draft_text
            approval_metadata = _deserialize_json(draft_row.metadata_json)

        if not draft_text:
            archetype_hint = _resolve_archetype_hint_for_outreach(session, contato, channel=channel)
            strategy = select_message_strategy(
                session,
                contato,
                channel=channel,
                archetype_hint=archetype_hint,
            )
            apply_inference_to_contact(contato, strategy)
            payload = build_personalized_draft(contato, channel=channel, strategy=strategy)
            draft_text = payload["draft"]
            approval_metadata = {
                "checks": payload.get("checks"),
                "strategy_key": payload.get("strategy_key"),
                "message_archetype": payload.get("message_archetype"),
                "messages": payload.get("messages"),
                "split_applied": payload.get("split_applied"),
            }

        approval = ContactInteraction(
            contato_id=contato.id,
            channel=channel,
            direction="internal",
            kind="approval",
            content_summary="Primeiro contato aprovado por humano.",
            approved_by=approved_by,
            draft_text=draft_text,
            metadata_json=_serialize_json(approval_metadata),
        )
        session.add(approval)
        _try_transition(contato, "approved", force=contato.readiness_status is None)
        contato.needs_human_review = False
        contato.updated_at = _utcnow()
        session.flush()
        return {"contact": contato.to_dict(), "approval": approval.to_dict()}


def send_whatsapp_outreach(
    contact_id: str,
    draft_interaction_id: str | None = None,
    messages: list[str] | None = None,
    require_approved: bool = True,
    content_summary: str | None = None,
    incoming_text: str | None = None,
    simulate_read_delay: bool = True,
    read_delay_ms: int | None = None,
) -> dict:
    with get_session() as session:
        contato = session.query(Contato).filter(Contato.id == contact_id, Contato.ativo == True).first()  # noqa: E712
        if not contato:
            return {"error": f"Contato {contact_id} não encontrado."}
        if contato.do_not_contact:
            return {"error": "Contato bloqueado por do_not_contact."}
        if contato.pipeline_status in {"fechado", "perdido"}:
            return {"error": f"Contato em status {contato.pipeline_status}. Não enviar novo contato."}
        if not _is_valid_phone(contato.whatsapp):
            return {"error": "Canal WhatsApp indisponível para este contato."}
        if require_approved and contato.needs_human_review:
            return {"error": "Envio bloqueado: primeiro toque ainda exige aprovação humana."}

        draft_row = None
        if draft_interaction_id:
            draft_row = (
                session.query(ContactInteraction)
                .filter(
                    ContactInteraction.id == draft_interaction_id,
                    ContactInteraction.contato_id == contact_id,
                    ContactInteraction.kind.in_(["draft", "approval"]),
                )
                .first()
            )
            if not draft_row:
                return {"error": f"Interação {draft_interaction_id} não encontrada para o contato."}
        else:
            draft_row = (
                session.query(ContactInteraction)
                .filter(
                    ContactInteraction.contato_id == contact_id,
                    ContactInteraction.kind.in_(["approval", "draft"]),
                )
                .order_by(ContactInteraction.created_at.desc())
                .first()
            )

        outbound_messages = _resolve_messages_for_whatsapp_send(
            session,
            contato,
            explicit_messages=messages,
            draft_row=draft_row,
        )
        if not outbound_messages:
            return {"error": "Nenhuma mensagem válida para envio."}

        now = _utcnow()
        read_delay_context: dict[str, Any] = {
            "simulate_read_delay": bool(simulate_read_delay),
            "incoming_source": None,
            "target_read_delay_ms": 0,
            "elapsed_since_inbound_ms": None,
            "applied_read_delay_ms": 0,
        }
        pre_read_delay_ms = 0
        if simulate_read_delay:
            if read_delay_ms is not None:
                pre_read_delay_ms = max(int(read_delay_ms), 0)
                read_delay_context["incoming_source"] = "explicit_read_delay_ms"
                read_delay_context["target_read_delay_ms"] = pre_read_delay_ms
            else:
                inbound_text = None
                inbound_at = None
                if (incoming_text or "").strip():
                    inbound_text = incoming_text.strip()
                    read_delay_context["incoming_source"] = "incoming_text_param"
                else:
                    latest_inbound = _resolve_last_inbound_interaction(session, contact_id)
                    if latest_inbound:
                        inbound_text = (latest_inbound.content_summary or "").strip()
                        inbound_at = latest_inbound.created_at
                        read_delay_context["incoming_source"] = "latest_inbound_interaction"
                    else:
                        read_delay_context["incoming_source"] = "fallback_default"

                target_read_delay_ms = human_read_delay_ms(inbound_text)
                read_delay_context["target_read_delay_ms"] = target_read_delay_ms

                if inbound_at:
                    elapsed_ms = max(int((now - inbound_at).total_seconds() * 1000), 0)
                    read_delay_context["elapsed_since_inbound_ms"] = elapsed_ms
                    pre_read_delay_ms = max(target_read_delay_ms - elapsed_ms, 0)
                else:
                    pre_read_delay_ms = target_read_delay_ms

        read_delay_context["applied_read_delay_ms"] = pre_read_delay_ms

        delivery = send_whatsapp_messages(
            contato.whatsapp or "",
            outbound_messages,
            pre_read_delay_ms=pre_read_delay_ms,
        )
        if "error" in delivery:
            return delivery

        draft_metadata = _deserialize_json(draft_row.metadata_json) if draft_row else {}
        metadata = {
            **draft_metadata,
            "delivery": delivery,
            "messages": outbound_messages,
            "source_draft_interaction_id": str(draft_row.id) if draft_row else None,
            "read_delay": read_delay_context,
        }

        sent_ok = bool(delivery.get("all_sent"))
        summary = content_summary or (
            "Mensagens WhatsApp enviadas com simulação de digitação."
            if sent_ok
            else "Falha parcial no envio de mensagens WhatsApp."
        )
        interaction = ContactInteraction(
            contato_id=contato.id,
            channel="whatsapp",
            direction="outbound",
            kind="conversation",
            content_summary=summary,
            outcome="sent" if sent_ok else "delivery_failed",
            draft_text="\n".join(outbound_messages),
            metadata_json=_serialize_json(metadata),
            sent_at=_utcnow(),
        )
        session.add(interaction)
        _try_transition(contato, "contacted", force=contato.readiness_status is None)
        contato.ultimo_contato = _utcnow()
        contato.updated_at = _utcnow()
        session.flush()
        return {
            "contact": contato.to_dict(),
            "interaction": interaction.to_dict(),
            "delivery": delivery,
            "messages": outbound_messages,
        }


def schedule_contact_task(
    contact_id: str,
    due_at: str | datetime,
    channel: str,
    objective: str,
    owner: str | None = None,
    priority: str = "medium",
    sla_hours: int | None = 24,
    sync_calendar: bool = True,
    reminder_at: str | datetime | None = None,
) -> dict:
    with get_session() as session:
        contato = session.query(Contato).filter(Contato.id == contact_id, Contato.ativo == True).first()  # noqa: E712
        if not contato:
            return {"error": f"Contato {contact_id} não encontrado."}
        due_dt = _parse_iso_datetime(due_at)
        if due_dt is None:
            return {"error": "due_at é obrigatório."}
        reminder_dt = _parse_iso_datetime(reminder_at)
        task = ContactTask(
            contato_id=contato.id,
            owner=owner,
            objective=objective,
            channel=channel,
            priority=priority,
            due_at=due_dt,
            reminder_at=reminder_dt,
            sla_hours=sla_hours,
            sync_calendar=sync_calendar,
        )
        session.add(task)
        session.flush()

        calendar_link = None
        if sync_calendar:
            calendar_link = CalendarLink(contato_id=contato.id, task_id=task.id)
            session.add(calendar_link)

        contato.updated_at = _utcnow()
        session.flush()
        return {
            "task": task.to_dict(),
            "calendar_link": calendar_link.to_dict() if calendar_link else None,
        }


def log_conversation_event(
    contact_id: str,
    channel: str,
    direction: str,
    content_summary: str,
    outcome: str | None = None,
    intent: str | None = None,
    metadata: dict | None = None,
    draft_interaction_id: str | None = None,
    stage_hops: int | None = None,
    sla_hours: int | None = None,
) -> dict:
    with get_session() as session:
        contato = session.query(Contato).filter(Contato.id == contact_id, Contato.ativo == True).first()  # noqa: E712
        if not contato:
            return {"error": f"Contato {contact_id} não encontrado."}

        metadata_payload: dict[str, Any] = dict(metadata or {})
        if direction == "inbound" and _is_bot_router_message(content_summary):
            metadata_payload["detected_bot_router"] = True
        linked_draft = None
        if draft_interaction_id:
            linked_draft = (
                session.query(ContactInteraction)
                .filter(
                    ContactInteraction.id == draft_interaction_id,
                    ContactInteraction.contato_id == contact_id,
                    ContactInteraction.kind == "draft",
                )
                .first()
            )
            if linked_draft:
                draft_meta = _deserialize_json(linked_draft.metadata_json)
                metadata_payload = {**draft_meta, **metadata_payload}

        normalized_outcome = outcome
        if outcome == "no_reply":
            reference_sent_at = _resolve_last_outbound_at(session, contact_id)
            elapsed_hours = None
            if reference_sent_at is not None:
                elapsed_hours = max((_utcnow() - reference_sent_at).total_seconds() / 3600.0, 0.0)
            normalized_outcome = resolve_sla_outcome(
                outcome,
                elapsed_hours=elapsed_hours,
                sla_hours=sla_hours if sla_hours is not None else _resolve_sla_hours(session, contact_id),
            )

        interaction = ContactInteraction(
            contato_id=contato.id,
            channel=channel,
            direction=direction,
            kind="conversation",
            content_summary=content_summary,
            outcome=normalized_outcome,
            intent=intent,
            metadata_json=_serialize_json(metadata_payload),
            sent_at=_utcnow() if direction == "outbound" else None,
        )
        session.add(interaction)

        if intent:
            contato.stage = intent

        if direction in {"outbound", "inbound"}:
            contato.ultimo_contato = _utcnow()

        if normalized_outcome in {"no_interest", "explicit_no_interest"}:
            contato.do_not_contact = True
            contato.do_not_contact_reason = "no_interest"
            contato.do_not_contact_at = _utcnow()
            contato.pipeline_status = "perdido"
            _try_transition(contato, "blocked", force=True)
        elif direction == "outbound":
            _try_transition(contato, "contacted", force=contato.readiness_status is None)
        elif direction == "inbound":
            _try_transition(contato, "follow_up", force=contato.readiness_status is None)

        strategy_learning = None
        strategy_key = metadata_payload.get("strategy_key")
        message_archetype = metadata_payload.get("message_archetype")
        if strategy_key and message_archetype and normalized_outcome:
            dimensions = resolve_contact_dimensions(
                contato,
                channel=channel,
                stage_override=(contato.pipeline_status or "lead"),
            )
            apply_inference_to_contact(contato, dimensions)
            strategy_learning = record_strategy_outcome(
                session,
                contato_id=contact_id,
                interaction_id=str(interaction.id),
                stage=dimensions["stage"],
                client_type=(metadata_payload.get("client_type") or dimensions["client_type"]),
                city=(metadata_payload.get("city") or dimensions["city"]),
                region=(metadata_payload.get("region") or dimensions["region"]),
                channel=channel,
                message_archetype=message_archetype,
                strategy_key=strategy_key,
                outcome=normalized_outcome,
                stage_hops=max(int(stage_hops or metadata_payload.get("stage_hops") or 0), 0),
                metadata=metadata_payload,
            )

        contato.updated_at = _utcnow()
        session.flush()
        return {
            "interaction": interaction.to_dict(),
            "contact": contato.to_dict(),
            "normalized_outcome": normalized_outcome,
            "strategy_learning": strategy_learning,
        }


def mark_no_interest(
    contact_id: str,
    reason: str | None = None,
    draft_interaction_id: str | None = None,
    metadata: dict | None = None,
) -> dict:
    with get_session() as session:
        contato = session.query(Contato).filter(Contato.id == contact_id, Contato.ativo == True).first()  # noqa: E712
        if not contato:
            return {"error": f"Contato {contact_id} não encontrado."}

        contato.do_not_contact = True
        contato.do_not_contact_reason = reason or "no_interest"
        contato.do_not_contact_at = _utcnow()
        contato.pipeline_status = "perdido"
        _try_transition(contato, "blocked", force=True)
        contato.updated_at = _utcnow()

        interaction = ContactInteraction(
            contato_id=contato.id,
            channel="whatsapp",
            direction="inbound",
            kind="conversation",
            content_summary="Contato sinalizou desinteresse e foi bloqueado.",
            outcome="no_interest",
            intent="desinteresse",
            metadata_json=_serialize_json({"reason": reason, **(metadata or {})}),
        )
        session.add(interaction)
        strategy_learning = None
        merged_metadata = dict(metadata or {})
        if draft_interaction_id:
            draft_row = (
                session.query(ContactInteraction)
                .filter(
                    ContactInteraction.id == draft_interaction_id,
                    ContactInteraction.contato_id == contact_id,
                    ContactInteraction.kind == "draft",
                )
                .first()
            )
            if draft_row:
                merged_metadata = {**_deserialize_json(draft_row.metadata_json), **merged_metadata}
        strategy_key = merged_metadata.get("strategy_key")
        message_archetype = merged_metadata.get("message_archetype")
        if strategy_key and message_archetype:
            dimensions = resolve_contact_dimensions(contato, channel="whatsapp", stage_override=(contato.pipeline_status or "lead"))
            strategy_learning = record_strategy_outcome(
                session,
                contato_id=contact_id,
                interaction_id=str(interaction.id),
                stage=dimensions["stage"],
                client_type=(merged_metadata.get("client_type") or dimensions["client_type"]),
                city=(merged_metadata.get("city") or dimensions["city"]),
                region=(merged_metadata.get("region") or dimensions["region"]),
                channel="whatsapp",
                message_archetype=message_archetype,
                strategy_key=strategy_key,
                outcome="no_interest",
                stage_hops=0,
                metadata=merged_metadata,
            )
        session.flush()
        return {"contact": contato.to_dict(), "interaction": interaction.to_dict(), "strategy_learning": strategy_learning}


def sync_calendar_links(
    limit: int = 20,
    status_filter: str = "pending_or_failed",
    calendar_id: str | None = None,
) -> dict:
    with get_session() as session:
        try:
            result = sync_calendar_links_worker(
                session,
                calendar_id=calendar_id,
                limit=limit,
                status_filter=status_filter,
            )
            session.flush()
            return result
        except Exception as exc:
            return {"error": f"Falha no sync do Google Calendar: {exc}"}


def send_daily_improvement_report(
    force: bool = False,
    channel_id: str | None = None,
    target: str | None = None,
) -> dict:
    with get_session() as session:
        try:
            result = send_daily_improvement_report_impl(
                session,
                force=force,
                channel_id=channel_id,
                target=target,
            )
            session.flush()
            return result
        except Exception as exc:
            return {"error": f"Falha no relatório diário de melhoria: {exc}"}


def buffer_incoming_messages(
    lead_id: str,
    event_text: str,
    *,
    channel: str = "whatsapp",
    message_id: str | None = None,
    max_hold_ms: int = 20000,
    max_msgs: int = 6,
    max_chars: int = 1000,
) -> dict:
    with get_session() as session:
        contato = session.query(Contato).filter(Contato.id == lead_id, Contato.ativo == True).first()  # noqa: E712
        if not contato:
            return {"error": f"Contato {lead_id} não encontrado."}

        text = (event_text or "").strip()
        if not text:
            return {"error": "event_text obrigatório."}

        now = _utcnow()
        open_buffer = (
            session.query(IncomingMessageBuffer)
            .filter(
                IncomingMessageBuffer.contato_id == contato.id,
                IncomingMessageBuffer.channel == channel,
                IncomingMessageBuffer.status == "open",
            )
            .order_by(IncomingMessageBuffer.created_at.desc())
            .first()
        )

        if not open_buffer:
            payload = {"messages": [], "message_ids": []}
            open_buffer = IncomingMessageBuffer(
                contato_id=contato.id,
                channel=channel,
                status="open",
                grouped_count=0,
                payload_json=_serialize_json(payload),
            )
            session.add(open_buffer)
            session.flush()

        payload = _deserialize_json(open_buffer.payload_json)
        messages = list(payload.get("messages") or [])
        message_ids = list(payload.get("message_ids") or [])
        if message_id and message_id in message_ids:
            grouped_count = int(open_buffer.grouped_count or len(messages))
            return {
                "lead_id": str(contato.id),
                "buffer_id": str(open_buffer.id),
                "status": "open",
                "grouped_count": grouped_count,
                "flush_reason": None,
                "payload": None,
                "idempotent": True,
            }

        messages.append(text)
        if message_id:
            message_ids.append(message_id)
        joined = " ".join(msg.strip() for msg in messages if (msg or "").strip())
        grouped_count = len(messages)

        elapsed_ms = max(int((now - open_buffer.created_at).total_seconds() * 1000), 0) if open_buffer.created_at else 0

        complete, completion_reason = _is_complete_message(joined)
        flush_reason = None
        if grouped_count >= max_msgs:
            flush_reason = "guardrail_count"
        elif len(joined) >= max_chars:
            flush_reason = "guardrail_size"
        elif complete:
            flush_reason = completion_reason
        elif elapsed_ms >= max_hold_ms:
            flush_reason = "guardrail_time"

        payload = {"messages": messages, "message_ids": message_ids, "joined_text": joined}
        open_buffer.payload_json = _serialize_json(payload)
        open_buffer.grouped_count = grouped_count
        open_buffer.updated_at = now

        if flush_reason:
            open_buffer.status = "flushed"
            open_buffer.flush_reason = flush_reason
            open_buffer.flushed_at = now
            return {
                "lead_id": str(contato.id),
                "buffer_id": str(open_buffer.id),
                "status": "flushed",
                "grouped_count": grouped_count,
                "flush_reason": flush_reason,
                "payload": {
                    "text": joined,
                    "messages": messages,
                    "channel": channel,
                },
                "idempotent": False,
            }

        return {
            "lead_id": str(contato.id),
            "buffer_id": str(open_buffer.id),
            "status": "open",
            "grouped_count": grouped_count,
            "flush_reason": None,
            "payload": None,
            "idempotent": False,
        }


def transcribe_incoming_audio(
    message_id: str,
    media_ref: str,
    *,
    transcript_hint: str | None = None,
) -> dict:
    if (transcript_hint or "").strip():
        return {
            "message_id": message_id,
            "text": transcript_hint.strip(),
            "confidence": 0.95,
            "provider": "hint",
        }

    ref = (media_ref or "").strip()
    if not ref:
        return {"error": "media_ref obrigatório."}

    if ref.lower().startswith("text:"):
        return {
            "message_id": message_id,
            "text": ref[5:].strip(),
            "confidence": 0.9,
            "provider": "text_ref",
        }

    m = re.search(r"transcript=([^&]+)", ref, flags=re.IGNORECASE)
    if m:
        try:
            from urllib.parse import unquote_plus

            text = unquote_plus(m.group(1)).strip()
            if text:
                return {
                    "message_id": message_id,
                    "text": text,
                    "confidence": 0.85,
                    "provider": "query_transcript",
                }
        except Exception:
            pass

    return {
        "message_id": message_id,
        "text": "",
        "confidence": 0.0,
        "provider": "unavailable",
        "error": "Transcrição automática indisponível. Informe transcript_hint ou media_ref com transcript.",
    }


def route_conversation_turn(
    payload: dict[str, Any],
) -> dict:
    text = str(payload.get("text") or "").strip()
    if not text and not payload.get("system_event"):
        return {"error": "payload.text obrigatório (ou system_event)."}

    system_event = str(payload.get("system_event") or "").strip() or None
    is_audio = bool(payload.get("is_audio"))
    intent, confidence = _detect_intent(text, system_event=system_event)
    specialist = INTENT_TO_SPECIALIST.get(intent, "qualifier-agent")
    policy_flags = _policy_flags_for_intent(intent, is_audio=is_audio)

    return {
        "intent": intent,
        "confidence": round(float(confidence), 4),
        "specialist": specialist,
        "policy_flags": policy_flags,
    }


def _resolve_last_internal_timeout(session, contato_id: str, event_type: str, reference_outbound_at: datetime | None) -> bool:
    query = (
        session.query(ContactInteraction)
        .filter(
            ContactInteraction.contato_id == contato_id,
            ContactInteraction.direction == "internal",
            ContactInteraction.kind == "system_event",
            ContactInteraction.outcome == event_type,
        )
        .order_by(ContactInteraction.created_at.desc())
    )
    row = query.first()
    if not row:
        return False
    if reference_outbound_at and row.created_at and row.created_at < reference_outbound_at:
        return False
    return True


def evaluate_dormant_leads(
    *,
    ruleset: dict[str, Any] | None = None,
    limit: int = 50,
) -> dict:
    now = _utcnow()
    cfg = dict(ruleset or {})
    first_sla = int(cfg.get("first_sla_hours", 24) or 24)
    second_sla = int(cfg.get("second_sla_hours", first_sla * 2) or (first_sla * 2))
    third_sla = int(cfg.get("third_sla_hours", max(second_sla + first_sla, 72)) or max(second_sla + first_sla, 72))
    pause_after_72h = bool(cfg.get("pause_after_72h", True))
    review_owner = str(cfg.get("pause_review_owner", "sales_manager"))
    review_channel = str(cfg.get("pause_review_channel", "discord"))
    windows = (
        ("timeout_72h", third_sla),
        ("timeout_48h", second_sla),
        ("timeout_24h", first_sla),
    )

    with get_session() as session:
        contatos = (
            session.query(Contato)
            .filter(
                Contato.ativo == True,  # noqa: E712
                Contato.do_not_contact == False,  # noqa: E712
                or_(
                    Contato.pipeline_status == None,  # noqa: E711
                    ~Contato.pipeline_status.in_(["fechado", "perdido", "follow_up_pause"]),
                ),
            )
            .limit(limit)
            .all()
        )

        triggered: list[dict[str, Any]] = []
        paused_contacts = 0
        created_review_tasks = 0
        skipped = 0
        for contato in contatos:
            last_outbound_at = _resolve_last_outbound_at(session, str(contato.id))
            if not last_outbound_at:
                skipped += 1
                continue

            latest_inbound = _resolve_last_inbound_interaction(session, str(contato.id))
            if latest_inbound and latest_inbound.created_at and latest_inbound.created_at > last_outbound_at:
                skipped += 1
                continue

            elapsed_hours = max((now - last_outbound_at).total_seconds() / 3600.0, 0.0)
            event_type = None
            threshold = None
            for candidate_event, threshold_hours in windows:
                if elapsed_hours >= threshold_hours:
                    event_type = candidate_event
                    threshold = threshold_hours
                    break
            if not event_type:
                skipped += 1
                continue

            already_triggered = _resolve_last_internal_timeout(
                session,
                str(contato.id),
                event_type=event_type,
                reference_outbound_at=last_outbound_at,
            )
            if already_triggered:
                skipped += 1
                continue

            interaction = ContactInteraction(
                contato_id=contato.id,
                channel="whatsapp",
                direction="internal",
                kind="system_event",
                content_summary=f"Evento proativo disparado: {event_type}",
                outcome=event_type,
                intent="proactive_follow_up",
                metadata_json=_serialize_json(
                    {
                        "deliver": False,
                        "event_type": event_type,
                        "elapsed_hours": round(elapsed_hours, 2),
                        "threshold_hours": threshold,
                    }
                ),
            )
            session.add(interaction)
            if pause_after_72h and event_type == "timeout_72h":
                contato.pipeline_status = "follow_up_pause"
                contato.updated_at = now
                paused_contacts += 1
                review_task = ContactTask(
                    contato_id=contato.id,
                    owner=review_owner,
                    objective="Revisar lead pausado apos 72h sem resposta e decidir proximo passo.",
                    channel=review_channel,
                    status="open",
                    priority="high",
                    due_at=now + timedelta(hours=4),
                    sla_hours=24,
                    sync_calendar=False,
                )
                session.add(review_task)
                created_review_tasks += 1

            triggered.append(
                {
                    "contact_id": str(contato.id),
                    "event_type": event_type,
                    "elapsed_hours": round(elapsed_hours, 2),
                    "interaction_id": str(interaction.id),
                }
            )

        return {
            "evaluated": len(contatos),
            "triggered": len(triggered),
            "paused_contacts": paused_contacts,
            "review_tasks_created": created_review_tasks,
            "skipped": skipped,
            "events": triggered,
            "windows_hours": {
                "timeout_24h": first_sla,
                "timeout_48h": second_sla,
                "timeout_72h": third_sla,
            },
        }


def start_feedback_review_session(
    batch_id: str,
    *,
    stage: str | None = None,
    city: str | None = None,
    client_type: str | None = None,
    thread_ref: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict:
    with get_session() as session:
        review_session = FeedbackReviewSession(
            batch_id=batch_id,
            stage=stage,
            city=city,
            client_type=client_type,
            status="open",
            thread_ref=thread_ref,
            metadata_json=_serialize_json(metadata),
        )
        session.add(review_session)
        session.flush()
        return {"session": review_session.to_dict()}


def record_human_feedback(
    session_id: str,
    feedback_text: str,
    *,
    tags: list[str] | None = None,
    author: str = "sales_reviewer",
    metadata: dict[str, Any] | None = None,
) -> dict:
    with get_session() as session:
        review_session = (
            session.query(FeedbackReviewSession)
            .filter(FeedbackReviewSession.id == session_id)
            .first()
        )
        if not review_session:
            return {"error": f"Sessão de review {session_id} não encontrada."}
        if review_session.status != "open":
            return {"error": f"Sessão {session_id} não está aberta para feedback."}

        entry = FeedbackReviewEntry(
            session_id=review_session.id,
            author=author or "sales_reviewer",
            feedback_text=(feedback_text or "").strip(),
            tags_json=_serialize_json({"tags": tags or []}),
            metadata_json=_serialize_json(metadata),
        )
        session.add(entry)
        review_session.updated_at = _utcnow()
        session.flush()
        return {"entry": entry.to_dict(), "session": review_session.to_dict()}


def _filtered_rankings_for_review(session, review_session: FeedbackReviewSession, top_n: int = 5) -> tuple[list[MessageStrategyRanking], list[MessageStrategyRanking]]:
    query = session.query(MessageStrategyRanking).filter(MessageStrategyRanking.attempts > 0)
    if review_session.stage:
        query = query.filter(MessageStrategyRanking.stage == review_session.stage)
    if review_session.city:
        query = query.filter(MessageStrategyRanking.city == review_session.city)
    if review_session.client_type:
        query = query.filter(MessageStrategyRanking.client_type == review_session.client_type)
    top = query.order_by(MessageStrategyRanking.smoothed_score.desc(), MessageStrategyRanking.attempts.desc()).limit(top_n).all()
    bottom = query.order_by(MessageStrategyRanking.smoothed_score.asc(), MessageStrategyRanking.attempts.desc()).limit(top_n).all()
    return top, bottom


def generate_strategy_update_proposal(
    session_id: str,
    *,
    proposed_by: str = "feedback-reviewer-agent",
    top_n: int = 5,
) -> dict:
    with get_session() as session:
        review_session = (
            session.query(FeedbackReviewSession)
            .filter(FeedbackReviewSession.id == session_id)
            .first()
        )
        if not review_session:
            return {"error": f"Sessão de review {session_id} não encontrada."}

        top_rankings, bottom_rankings = _filtered_rankings_for_review(session, review_session, top_n=top_n)
        feedback_entries = (
            session.query(FeedbackReviewEntry)
            .filter(FeedbackReviewEntry.session_id == review_session.id)
            .order_by(FeedbackReviewEntry.created_at.asc())
            .all()
        )
        feedback_texts = [entry.feedback_text for entry in feedback_entries]
        snapshot = build_daily_improvement_snapshot(session, top_n=top_n)

        adjustments: list[dict[str, Any]] = []
        for row in top_rankings:
            adjustments.append(
                {
                    "action": "promote",
                    "strategy_key": row.strategy_key,
                    "score_delta": 2.0,
                }
            )
        for row in bottom_rankings:
            adjustments.append(
                {
                    "action": "demote",
                    "strategy_key": row.strategy_key,
                    "score_delta": -2.0,
                }
            )

        normalized_feedback = " ".join(feedback_texts).lower()
        if "pausa" in normalized_feedback or "parar" in normalized_feedback:
            for row in bottom_rankings[:2]:
                adjustments.append(
                    {
                        "action": "pause",
                        "strategy_key": row.strategy_key,
                        "score_delta": -6.0,
                    }
                )

        proposal_batch_id = f"proposal-{uuid.uuid4().hex[:12]}"
        proposal_payload = {
            "scope": {
                "batch_id": review_session.batch_id,
                "stage": review_session.stage,
                "city": review_session.city,
                "client_type": review_session.client_type,
            },
            "feedback": feedback_texts,
            "snapshot": snapshot,
            "adjustments": adjustments,
            "generated_at": _utcnow().isoformat(),
        }
        proposal = StrategyUpdateProposal(
            session_id=review_session.id,
            proposal_batch_id=proposal_batch_id,
            status="pending_approval",
            proposed_by=proposed_by,
            proposal_json=_serialize_json(proposal_payload) or "{}",
            decision_notes="auto_submitted_from_draft_review",
        )
        session.add(proposal)
        review_session.updated_at = _utcnow()
        session.flush()
        return {"proposal": proposal.to_dict(), "payload": proposal_payload}


def _apply_strategy_adjustment(session, item: dict[str, Any], *, now: datetime) -> bool:
    strategy_key = str(item.get("strategy_key") or "").strip()
    if not strategy_key:
        return False
    row = session.query(MessageStrategyRanking).filter(MessageStrategyRanking.strategy_key == strategy_key).first()
    if not row:
        return False

    score_delta = float(item.get("score_delta", 0.0))
    if score_delta == 0.0:
        return False

    updated = update_strategy_ranking(
        session,
        stage=row.stage,
        client_type=row.client_type,
        city=row.city,
        region=row.region,
        channel=row.channel,
        message_archetype=row.message_archetype,
        strategy_key=row.strategy_key,
        score_delta=score_delta,
        outcome_at=now,
    )
    if item.get("action") == "pause":
        updated.low_confidence = True
    return True


def approve_strategy_updates(
    proposal_batch_id: str,
    approver: str,
    *,
    decision_notes: str | None = None,
) -> dict:
    with get_session() as session:
        proposal = (
            session.query(StrategyUpdateProposal)
            .filter(StrategyUpdateProposal.proposal_batch_id == proposal_batch_id)
            .first()
        )
        if not proposal:
            return {"error": f"Proposal {proposal_batch_id} não encontrada."}
        if proposal.status != "pending_approval":
            return {"error": f"Proposal {proposal_batch_id} em status inválido: {proposal.status}."}

        payload = _deserialize_json(proposal.proposal_json)
        adjustments = payload.get("adjustments") if isinstance(payload, dict) else []
        now = _utcnow()
        applied_count = 0
        for item in adjustments if isinstance(adjustments, list) else []:
            if isinstance(item, dict) and _apply_strategy_adjustment(session, item, now=now):
                applied_count += 1

        proposal.status = "approved"
        proposal.approved_by = approver
        proposal.rejected_reason = None
        proposal.decision_notes = decision_notes
        proposal.updated_at = now

        review_session = (
            session.query(FeedbackReviewSession)
            .filter(FeedbackReviewSession.id == proposal.session_id)
            .first()
        )
        if review_session:
            review_session.status = "closed"
            review_session.updated_at = now
        session.flush()
        return {"proposal": proposal.to_dict(), "applied_adjustments": applied_count}


def reject_strategy_updates(
    proposal_batch_id: str,
    reason: str,
) -> dict:
    with get_session() as session:
        proposal = (
            session.query(StrategyUpdateProposal)
            .filter(StrategyUpdateProposal.proposal_batch_id == proposal_batch_id)
            .first()
        )
        if not proposal:
            return {"error": f"Proposal {proposal_batch_id} não encontrada."}
        if proposal.status not in {"pending_approval", "draft_review"}:
            return {"error": f"Proposal {proposal_batch_id} em status inválido: {proposal.status}."}

        proposal.status = "rejected"
        proposal.rejected_reason = reason
        proposal.updated_at = _utcnow()
        review_session = (
            session.query(FeedbackReviewSession)
            .filter(FeedbackReviewSession.id == proposal.session_id)
            .first()
        )
        if review_session:
            review_session.status = "closed"
            review_session.updated_at = _utcnow()
        session.flush()
        return {"proposal": proposal.to_dict()}


def list_contacts_to_follow_up(hours_since_last_contact: int = 24, limit: int = 10) -> list[dict]:
    """Retorna contatos elegíveis para abordagem proativa.

    Critérios:
    - pipeline_status não é 'fechado' nem 'perdido'
    - do_not_contact = false
    - ultimo_contato é NULL ou mais antigo que hours_since_last_contact
    - ordem: nunca contactados primeiro, depois os mais antigos
    """
    cutoff = _utcnow() - timedelta(hours=hours_since_last_contact)

    with get_session() as session:
        results = (
            session.query(Contato)
            .filter(
                Contato.ativo == True,  # noqa: E712
                Contato.do_not_contact == False,  # noqa: E712
                or_(
                    Contato.pipeline_status == None,  # noqa: E711
                    ~Contato.pipeline_status.in_(["fechado", "perdido"]),
                ),
                or_(
                    Contato.ultimo_contato == None,  # noqa: E711
                    Contato.ultimo_contato < cutoff,
                ),
            )
            .order_by(Contato.ultimo_contato.asc().nullsfirst())
            .limit(limit)
            .all()
        )
        return [c.to_dict() for c in results]


def search_contatos(query: str, limite: int = 10) -> list[dict]:
    like = f"%{query}%"
    with get_session() as session:
        results = (
            session.query(Contato)
            .filter(
                Contato.ativo == True,  # noqa: E712
                or_(
                    Contato.nome.ilike(like),
                    Contato.apelido.ilike(like),
                    Contato.empresa.ilike(like),
                    Contato.email.ilike(like),
                    Contato.telefone.ilike(like),
                    Contato.whatsapp.ilike(like),
                    Contato.linkedin.ilike(like),
                    Contato.instagram.ilike(like),
                ),
            )
            .order_by(Contato.nome.asc())
            .limit(limite)
            .all()
        )
        return [c.to_dict() for c in results]
