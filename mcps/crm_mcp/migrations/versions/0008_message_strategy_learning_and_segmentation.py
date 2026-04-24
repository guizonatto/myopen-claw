"""add segmentation fields and message strategy learning tables

Revision ID: 0008
Revises: 0007
Create Date: 2026-04-23
"""

from alembic import op
import sqlalchemy as sa
import sqlalchemy.dialects.postgresql as pg


revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None
SCHEMA = "crm_mcp"


def upgrade():
    op.add_column("contatos", sa.Column("region", sa.Text(), nullable=True), schema=SCHEMA)
    op.add_column("contatos", sa.Column("client_type", sa.Text(), nullable=True), schema=SCHEMA)
    op.add_column(
        "contatos",
        sa.Column("inferred_region", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        schema=SCHEMA,
    )
    op.add_column(
        "contatos",
        sa.Column("inferred_client_type", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        schema=SCHEMA,
    )
    op.create_index("idx_contatos_region_client_type", "contatos", ["region", "client_type"], schema=SCHEMA)

    op.create_table(
        "message_strategy_outcomes",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("contato_id", pg.UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.contatos.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "interaction_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey(f"{SCHEMA}.contact_interactions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("stage", sa.Text(), nullable=False),
        sa.Column("client_type", sa.Text(), nullable=False),
        sa.Column("region", sa.Text(), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("message_archetype", sa.Text(), nullable=False),
        sa.Column("strategy_key", sa.Text(), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("stage_hops", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("score_delta", sa.Float(), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        schema=SCHEMA,
    )
    op.create_index("idx_message_strategy_outcomes_strategy_key", "message_strategy_outcomes", ["strategy_key"], schema=SCHEMA)
    op.create_index("idx_message_strategy_outcomes_created_at", "message_strategy_outcomes", ["created_at"], schema=SCHEMA)

    op.create_table(
        "message_strategy_rankings",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("stage", sa.Text(), nullable=False),
        sa.Column("client_type", sa.Text(), nullable=False),
        sa.Column("region", sa.Text(), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("message_archetype", sa.Text(), nullable=False),
        sa.Column("strategy_key", sa.Text(), nullable=False, unique=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_outcome_points", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("smoothed_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("low_confidence", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_outcome_at", sa.DateTime(timezone=True), nullable=True),
        schema=SCHEMA,
    )
    op.create_index(
        "idx_message_strategy_rankings_lookup",
        "message_strategy_rankings",
        ["stage", "client_type", "region", "channel", "message_archetype"],
        schema=SCHEMA,
    )


def downgrade():
    op.drop_index("idx_message_strategy_rankings_lookup", table_name="message_strategy_rankings", schema=SCHEMA)
    op.drop_table("message_strategy_rankings", schema=SCHEMA)

    op.drop_index("idx_message_strategy_outcomes_created_at", table_name="message_strategy_outcomes", schema=SCHEMA)
    op.drop_index("idx_message_strategy_outcomes_strategy_key", table_name="message_strategy_outcomes", schema=SCHEMA)
    op.drop_table("message_strategy_outcomes", schema=SCHEMA)

    op.drop_index("idx_contatos_region_client_type", table_name="contatos", schema=SCHEMA)
    op.drop_column("contatos", "inferred_client_type", schema=SCHEMA)
    op.drop_column("contatos", "inferred_region", schema=SCHEMA)
    op.drop_column("contatos", "client_type", schema=SCHEMA)
    op.drop_column("contatos", "region", schema=SCHEMA)
