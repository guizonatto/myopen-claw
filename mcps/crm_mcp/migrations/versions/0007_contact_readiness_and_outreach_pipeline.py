"""add readiness, enrichment and outreach pipeline tables

Revision ID: 0007
Revises: 0006
Create Date: 2026-04-23
"""

from alembic import op
import sqlalchemy as sa
import sqlalchemy.dialects.postgresql as pg


revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None
SCHEMA = "crm_mcp"


def upgrade():
    op.add_column("contatos", sa.Column("readiness_status", sa.Text(), nullable=True, server_default="ingested"), schema=SCHEMA)
    op.add_column("contatos", sa.Column("readiness_score", sa.Integer(), nullable=True), schema=SCHEMA)
    op.add_column("contatos", sa.Column("verified_signals_count", sa.Integer(), nullable=False, server_default="0"), schema=SCHEMA)
    op.add_column("contatos", sa.Column("last_enriched_at", sa.DateTime(timezone=True), nullable=True), schema=SCHEMA)
    op.add_column("contatos", sa.Column("fresh_until", sa.DateTime(timezone=True), nullable=True), schema=SCHEMA)
    op.add_column("contatos", sa.Column("needs_human_review", sa.Boolean(), nullable=False, server_default=sa.text("true")), schema=SCHEMA)
    op.add_column("contatos", sa.Column("do_not_contact", sa.Boolean(), nullable=False, server_default=sa.text("false")), schema=SCHEMA)
    op.add_column("contatos", sa.Column("do_not_contact_reason", sa.Text(), nullable=True), schema=SCHEMA)
    op.add_column("contatos", sa.Column("do_not_contact_at", sa.DateTime(timezone=True), nullable=True), schema=SCHEMA)
    op.add_column("contatos", sa.Column("persona_profile", sa.Text(), nullable=True), schema=SCHEMA)
    op.add_column("contatos", sa.Column("pain_hypothesis", sa.Text(), nullable=True), schema=SCHEMA)
    op.add_column("contatos", sa.Column("recent_signal", sa.Text(), nullable=True), schema=SCHEMA)
    op.add_column("contatos", sa.Column("offer_fit", sa.Text(), nullable=True), schema=SCHEMA)
    op.add_column("contatos", sa.Column("preferred_tone", sa.Text(), nullable=True), schema=SCHEMA)
    op.add_column("contatos", sa.Column("best_contact_window", sa.Text(), nullable=True), schema=SCHEMA)

    op.create_index("idx_contatos_readiness_status", "contatos", ["readiness_status"], schema=SCHEMA)
    op.create_index("idx_contatos_do_not_contact", "contatos", ["do_not_contact"], schema=SCHEMA)
    op.create_index("idx_contatos_fresh_until", "contatos", ["fresh_until"], schema=SCHEMA)

    op.create_table(
        "contact_enrichment_runs",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("contato_id", pg.UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.contatos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mode", sa.Text(), nullable=False, server_default="deep"),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column("divergence_whatsapp", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("divergence_email", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("divergence_company_or_cnpj", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("notes", sa.Text(), nullable=True),
        schema=SCHEMA,
    )
    op.create_index("idx_enrichment_contato", "contact_enrichment_runs", ["contato_id"], schema=SCHEMA)
    op.create_index("idx_enrichment_created_at", "contact_enrichment_runs", ["created_at"], schema=SCHEMA)

    op.create_table(
        "contact_interactions",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("contato_id", pg.UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.contatos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("direction", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False, server_default="conversation"),
        sa.Column("content_summary", sa.Text(), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=True),
        sa.Column("intent", sa.Text(), nullable=True),
        sa.Column("approved_by", sa.Text(), nullable=True),
        sa.Column("draft_text", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        schema=SCHEMA,
    )
    op.create_index("idx_interactions_contato", "contact_interactions", ["contato_id"], schema=SCHEMA)
    op.create_index("idx_interactions_channel", "contact_interactions", ["channel"], schema=SCHEMA)
    op.create_index("idx_interactions_created_at", "contact_interactions", ["created_at"], schema=SCHEMA)

    op.create_table(
        "contact_tasks",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("contato_id", pg.UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.contatos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner", sa.Text(), nullable=True),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="open"),
        sa.Column("priority", sa.Text(), nullable=False, server_default="medium"),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reminder_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sla_hours", sa.Integer(), nullable=True),
        sa.Column("sync_calendar", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        schema=SCHEMA,
    )
    op.create_index("idx_tasks_contato", "contact_tasks", ["contato_id"], schema=SCHEMA)
    op.create_index("idx_tasks_status_due", "contact_tasks", ["status", "due_at"], schema=SCHEMA)

    op.create_table(
        "calendar_links",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("contato_id", pg.UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.contatos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id", pg.UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.contact_tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False, server_default="google_calendar"),
        sa.Column("calendar_event_id", sa.Text(), nullable=True),
        sa.Column("sync_status", sa.Text(), nullable=False, server_default="pending_sync"),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sync_error", sa.Text(), nullable=True),
        schema=SCHEMA,
    )
    op.create_index("idx_calendar_links_task", "calendar_links", ["task_id"], schema=SCHEMA)
    op.create_index("idx_calendar_links_status", "calendar_links", ["sync_status"], schema=SCHEMA)


def downgrade():
    op.drop_index("idx_calendar_links_status", table_name="calendar_links", schema=SCHEMA)
    op.drop_index("idx_calendar_links_task", table_name="calendar_links", schema=SCHEMA)
    op.drop_table("calendar_links", schema=SCHEMA)

    op.drop_index("idx_tasks_status_due", table_name="contact_tasks", schema=SCHEMA)
    op.drop_index("idx_tasks_contato", table_name="contact_tasks", schema=SCHEMA)
    op.drop_table("contact_tasks", schema=SCHEMA)

    op.drop_index("idx_interactions_created_at", table_name="contact_interactions", schema=SCHEMA)
    op.drop_index("idx_interactions_channel", table_name="contact_interactions", schema=SCHEMA)
    op.drop_index("idx_interactions_contato", table_name="contact_interactions", schema=SCHEMA)
    op.drop_table("contact_interactions", schema=SCHEMA)

    op.drop_index("idx_enrichment_created_at", table_name="contact_enrichment_runs", schema=SCHEMA)
    op.drop_index("idx_enrichment_contato", table_name="contact_enrichment_runs", schema=SCHEMA)
    op.drop_table("contact_enrichment_runs", schema=SCHEMA)

    op.drop_index("idx_contatos_fresh_until", table_name="contatos", schema=SCHEMA)
    op.drop_index("idx_contatos_do_not_contact", table_name="contatos", schema=SCHEMA)
    op.drop_index("idx_contatos_readiness_status", table_name="contatos", schema=SCHEMA)

    op.drop_column("contatos", "best_contact_window", schema=SCHEMA)
    op.drop_column("contatos", "preferred_tone", schema=SCHEMA)
    op.drop_column("contatos", "offer_fit", schema=SCHEMA)
    op.drop_column("contatos", "recent_signal", schema=SCHEMA)
    op.drop_column("contatos", "pain_hypothesis", schema=SCHEMA)
    op.drop_column("contatos", "persona_profile", schema=SCHEMA)
    op.drop_column("contatos", "do_not_contact_at", schema=SCHEMA)
    op.drop_column("contatos", "do_not_contact_reason", schema=SCHEMA)
    op.drop_column("contatos", "do_not_contact", schema=SCHEMA)
    op.drop_column("contatos", "needs_human_review", schema=SCHEMA)
    op.drop_column("contatos", "fresh_until", schema=SCHEMA)
    op.drop_column("contatos", "last_enriched_at", schema=SCHEMA)
    op.drop_column("contatos", "verified_signals_count", schema=SCHEMA)
    op.drop_column("contatos", "readiness_score", schema=SCHEMA)
    op.drop_column("contatos", "readiness_status", schema=SCHEMA)
