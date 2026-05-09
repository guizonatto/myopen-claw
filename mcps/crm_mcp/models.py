import uuid
from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, Text
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql import func
from sqlalchemy import MetaData
from pgvector.sqlalchemy import Vector

class Base(DeclarativeBase):
    metadata = MetaData(schema="crm_mcp")


class SerializableMixin:
    def to_dict(self) -> dict:
        result = {}
        for c in self.__table__.columns:
            val = getattr(self, c.name)
            if isinstance(val, uuid.UUID):
                val = str(val)
            elif isinstance(val, datetime):
                val = val.isoformat()
            result[c.name] = val
        return result


class Contato(Base, SerializableMixin):
    __tablename__ = 'contatos'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    nome = Column(Text, nullable=False)
    apelido = Column(Text, nullable=True)
    tipo = Column(Text, nullable=True)
    aniversario = Column(DateTime, nullable=True)
    telefone = Column(Text, nullable=True)
    whatsapp = Column(Text, nullable=True)
    email = Column(Text, nullable=True)
    linkedin = Column(Text, nullable=True)
    instagram = Column(Text, nullable=True)
    empresa = Column(Text, nullable=True)
    cargo = Column(Text, nullable=True)
    setor = Column(Text, nullable=True)
    city = Column(Text, nullable=True)
    region = Column(Text, nullable=True)
    client_type = Column(Text, nullable=True)
    inferred_city = Column(Boolean, nullable=False, server_default='false')
    inferred_region = Column(Boolean, nullable=False, server_default='false')
    inferred_client_type = Column(Boolean, nullable=False, server_default='false')
    cnpj = Column(Text, nullable=True)
    cnaes = Column(ARRAY(Text), nullable=True)
    pipeline_status = Column(Text, nullable=True)
    stage = Column(Text, nullable=True)
    icp_type = Column(Text, nullable=True)
    readiness_status = Column(Text, nullable=True, server_default='ingested')
    readiness_score = Column(Integer, nullable=True)
    verified_signals_count = Column(Integer, nullable=False, server_default='0')
    last_enriched_at = Column(DateTime(timezone=True), nullable=True)
    fresh_until = Column(DateTime(timezone=True), nullable=True)
    needs_human_review = Column(Boolean, nullable=False, server_default='true')
    do_not_contact = Column(Boolean, nullable=False, server_default='false')
    do_not_contact_reason = Column(Text, nullable=True)
    do_not_contact_at = Column(DateTime(timezone=True), nullable=True)
    persona_profile = Column(Text, nullable=True)
    pain_hypothesis = Column(Text, nullable=True)
    recent_signal = Column(Text, nullable=True)
    offer_fit = Column(Text, nullable=True)
    preferred_tone = Column(Text, nullable=True)
    best_contact_window = Column(Text, nullable=True)
    notas = Column(Text, nullable=True)
    ativo = Column(Boolean, server_default='true')
    ultimo_contato = Column(DateTime(timezone=True), nullable=True)
    embedding = Column(Vector(1536), nullable=True)

class ContatoRelacionamento(Base, SerializableMixin):
    __tablename__ = 'contato_relacionamentos'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    contato_id = Column(UUID(as_uuid=True), ForeignKey('crm_mcp.contatos.id', ondelete='CASCADE'), nullable=False)
    relacionado_id = Column(UUID(as_uuid=True), ForeignKey('crm_mcp.contatos.id', ondelete='CASCADE'), nullable=False)
    tipo = Column(Text, nullable=False)
    notas = Column(Text, nullable=True)

class ContactEnrichmentRun(Base, SerializableMixin):
    __tablename__ = 'contact_enrichment_runs'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    contato_id = Column(UUID(as_uuid=True), ForeignKey('crm_mcp.contatos.id', ondelete='CASCADE'), nullable=False)
    mode = Column(Text, nullable=False, server_default='deep')
    source = Column(Text, nullable=True)
    confidence = Column(Float, nullable=False, server_default='0.0')
    evidence = Column(Text, nullable=True)
    divergence_whatsapp = Column(Boolean, nullable=False, server_default='false')
    divergence_email = Column(Boolean, nullable=False, server_default='false')
    divergence_company_or_cnpj = Column(Boolean, nullable=False, server_default='false')
    notes = Column(Text, nullable=True)


class ContactInteraction(Base, SerializableMixin):
    __tablename__ = 'contact_interactions'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    contato_id = Column(UUID(as_uuid=True), ForeignKey('crm_mcp.contatos.id', ondelete='CASCADE'), nullable=False)
    channel = Column(Text, nullable=False)
    direction = Column(Text, nullable=False)
    kind = Column(Text, nullable=False, server_default='conversation')
    content_summary = Column(Text, nullable=False)
    outcome = Column(Text, nullable=True)
    intent = Column(Text, nullable=True)
    approved_by = Column(Text, nullable=True)
    draft_text = Column(Text, nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    metadata_json = Column(Text, nullable=True)


class ContactTask(Base, SerializableMixin):
    __tablename__ = 'contact_tasks'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    contato_id = Column(UUID(as_uuid=True), ForeignKey('crm_mcp.contatos.id', ondelete='CASCADE'), nullable=False)
    owner = Column(Text, nullable=True)
    objective = Column(Text, nullable=False)
    channel = Column(Text, nullable=False)
    status = Column(Text, nullable=False, server_default='open')
    priority = Column(Text, nullable=False, server_default='medium')
    due_at = Column(DateTime(timezone=True), nullable=False)
    reminder_at = Column(DateTime(timezone=True), nullable=True)
    sla_hours = Column(Integer, nullable=True)
    sync_calendar = Column(Boolean, nullable=False, server_default='false')


class CalendarLink(Base, SerializableMixin):
    __tablename__ = 'calendar_links'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    contato_id = Column(UUID(as_uuid=True), ForeignKey('crm_mcp.contatos.id', ondelete='CASCADE'), nullable=False)
    task_id = Column(UUID(as_uuid=True), ForeignKey('crm_mcp.contact_tasks.id', ondelete='CASCADE'), nullable=False)
    provider = Column(Text, nullable=False, server_default='google_calendar')
    calendar_event_id = Column(Text, nullable=True)
    sync_status = Column(Text, nullable=False, server_default='pending_sync')
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    sync_error = Column(Text, nullable=True)


class MessageStrategyOutcome(Base, SerializableMixin):
    __tablename__ = 'message_strategy_outcomes'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    contato_id = Column(UUID(as_uuid=True), ForeignKey('crm_mcp.contatos.id', ondelete='CASCADE'), nullable=False)
    interaction_id = Column(UUID(as_uuid=True), ForeignKey('crm_mcp.contact_interactions.id', ondelete='SET NULL'), nullable=True)
    stage = Column(Text, nullable=False)
    client_type = Column(Text, nullable=False)
    city = Column(Text, nullable=False)
    region = Column(Text, nullable=False)
    channel = Column(Text, nullable=False)
    message_archetype = Column(Text, nullable=False)
    strategy_key = Column(Text, nullable=False)
    outcome = Column(Text, nullable=False)
    stage_hops = Column(Integer, nullable=False, server_default='0')
    score_delta = Column(Float, nullable=False)
    metadata_json = Column(Text, nullable=True)


class MessageStrategyRanking(Base, SerializableMixin):
    __tablename__ = 'message_strategy_rankings'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    stage = Column(Text, nullable=False)
    client_type = Column(Text, nullable=False)
    city = Column(Text, nullable=False)
    region = Column(Text, nullable=False)
    channel = Column(Text, nullable=False)
    message_archetype = Column(Text, nullable=False)
    strategy_key = Column(Text, nullable=False, unique=True)
    attempts = Column(Integer, nullable=False, server_default='0')
    total_outcome_points = Column(Float, nullable=False, server_default='0.0')
    smoothed_score = Column(Float, nullable=False, server_default='0.0')
    confidence = Column(Float, nullable=False, server_default='0.0')
    low_confidence = Column(Boolean, nullable=False, server_default='true')
    last_outcome_at = Column(DateTime(timezone=True), nullable=True)


Index(
    'idx_message_strategy_rankings_lookup',
    MessageStrategyRanking.stage,
    MessageStrategyRanking.client_type,
    MessageStrategyRanking.city,
    MessageStrategyRanking.region,
    MessageStrategyRanking.channel,
    MessageStrategyRanking.message_archetype,
)

Index('idx_message_strategy_outcomes_strategy_key', MessageStrategyOutcome.strategy_key)


class IncomingMessageBuffer(Base, SerializableMixin):
    __tablename__ = "incoming_message_buffers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    contato_id = Column(UUID(as_uuid=True), ForeignKey("crm_mcp.contatos.id", ondelete="CASCADE"), nullable=False)
    channel = Column(Text, nullable=False, server_default="whatsapp")
    status = Column(Text, nullable=False, server_default="open")
    flush_reason = Column(Text, nullable=True)
    grouped_count = Column(Integer, nullable=False, server_default="0")
    payload_json = Column(Text, nullable=True)
    flushed_at = Column(DateTime(timezone=True), nullable=True)


class FeedbackReviewSession(Base, SerializableMixin):
    __tablename__ = "feedback_review_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    batch_id = Column(Text, nullable=False)
    stage = Column(Text, nullable=True)
    city = Column(Text, nullable=True)
    client_type = Column(Text, nullable=True)
    status = Column(Text, nullable=False, server_default="open")
    channel = Column(Text, nullable=False, server_default="discord")
    thread_ref = Column(Text, nullable=True)
    metadata_json = Column(Text, nullable=True)


class FeedbackReviewEntry(Base, SerializableMixin):
    __tablename__ = "feedback_review_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("crm_mcp.feedback_review_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    author = Column(Text, nullable=False, server_default="sales_reviewer")
    feedback_text = Column(Text, nullable=False)
    tags_json = Column(Text, nullable=True)
    metadata_json = Column(Text, nullable=True)


class StrategyUpdateProposal(Base, SerializableMixin):
    __tablename__ = "strategy_update_proposals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("crm_mcp.feedback_review_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    proposal_batch_id = Column(Text, nullable=False, unique=True)
    status = Column(Text, nullable=False, server_default="draft_review")
    proposed_by = Column(Text, nullable=True)
    approved_by = Column(Text, nullable=True)
    rejected_reason = Column(Text, nullable=True)
    proposal_json = Column(Text, nullable=False)
    decision_notes = Column(Text, nullable=True)


class OperationAuditLog(Base, SerializableMixin):
    __tablename__ = "operation_audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    actor = Column(Text, nullable=False, server_default="system")
    role = Column(Text, nullable=False, server_default="system")
    operation = Column(Text, nullable=False)
    resource_id = Column(Text, nullable=True)
    status = Column(Text, nullable=False)
    reason = Column(Text, nullable=True)
    before_json = Column(Text, nullable=True)
    after_json = Column(Text, nullable=True)
    error = Column(Text, nullable=True)


Index("idx_incoming_message_buffers_lookup", IncomingMessageBuffer.contato_id, IncomingMessageBuffer.status)
Index("idx_feedback_review_sessions_batch", FeedbackReviewSession.batch_id, FeedbackReviewSession.status)
Index("idx_feedback_review_entries_session", FeedbackReviewEntry.session_id, FeedbackReviewEntry.created_at)
Index("idx_strategy_update_proposals_status", StrategyUpdateProposal.status, StrategyUpdateProposal.created_at)
Index("idx_operation_audit_logs_lookup", OperationAuditLog.operation, OperationAuditLog.status, OperationAuditLog.created_at)
