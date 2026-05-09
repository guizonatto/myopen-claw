"""add inbound buffer and feedback review proposal tables

Revision ID: 0010
Revises: 0009
Create Date: 2026-04-25
"""

from alembic import op
import sqlalchemy as sa
import sqlalchemy.dialects.postgresql as pg


revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None
SCHEMA = "crm_mcp"


def upgrade():
    op.create_table(
        "incoming_message_buffers",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("contato_id", pg.UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.contatos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False, server_default="whatsapp"),
        sa.Column("status", sa.Text(), nullable=False, server_default="open"),
        sa.Column("flush_reason", sa.Text(), nullable=True),
        sa.Column("grouped_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("flushed_at", sa.DateTime(timezone=True), nullable=True),
        schema=SCHEMA,
    )
    op.create_index(
        "idx_incoming_message_buffers_lookup",
        "incoming_message_buffers",
        ["contato_id", "status"],
        schema=SCHEMA,
    )

    op.create_table(
        "feedback_review_sessions",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("batch_id", sa.Text(), nullable=False),
        sa.Column("stage", sa.Text(), nullable=True),
        sa.Column("city", sa.Text(), nullable=True),
        sa.Column("client_type", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="open"),
        sa.Column("channel", sa.Text(), nullable=False, server_default="discord"),
        sa.Column("thread_ref", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        schema=SCHEMA,
    )
    op.create_index("idx_feedback_review_sessions_batch", "feedback_review_sessions", ["batch_id", "status"], schema=SCHEMA)

    op.create_table(
        "feedback_review_entries",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column(
            "session_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey(f"{SCHEMA}.feedback_review_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("author", sa.Text(), nullable=False, server_default="sales_reviewer"),
        sa.Column("feedback_text", sa.Text(), nullable=False),
        sa.Column("tags_json", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        schema=SCHEMA,
    )
    op.create_index("idx_feedback_review_entries_session", "feedback_review_entries", ["session_id", "created_at"], schema=SCHEMA)

    op.create_table(
        "strategy_update_proposals",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column(
            "session_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey(f"{SCHEMA}.feedback_review_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("proposal_batch_id", sa.Text(), nullable=False, unique=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="draft_review"),
        sa.Column("proposed_by", sa.Text(), nullable=True),
        sa.Column("approved_by", sa.Text(), nullable=True),
        sa.Column("rejected_reason", sa.Text(), nullable=True),
        sa.Column("proposal_json", sa.Text(), nullable=False),
        sa.Column("decision_notes", sa.Text(), nullable=True),
        schema=SCHEMA,
    )
    op.create_index(
        "idx_strategy_update_proposals_status",
        "strategy_update_proposals",
        ["status", "created_at"],
        schema=SCHEMA,
    )


def downgrade():
    op.drop_index("idx_strategy_update_proposals_status", table_name="strategy_update_proposals", schema=SCHEMA)
    op.drop_table("strategy_update_proposals", schema=SCHEMA)

    op.drop_index("idx_feedback_review_entries_session", table_name="feedback_review_entries", schema=SCHEMA)
    op.drop_table("feedback_review_entries", schema=SCHEMA)

    op.drop_index("idx_feedback_review_sessions_batch", table_name="feedback_review_sessions", schema=SCHEMA)
    op.drop_table("feedback_review_sessions", schema=SCHEMA)

    op.drop_index("idx_incoming_message_buffers_lookup", table_name="incoming_message_buffers", schema=SCHEMA)
    op.drop_table("incoming_message_buffers", schema=SCHEMA)
