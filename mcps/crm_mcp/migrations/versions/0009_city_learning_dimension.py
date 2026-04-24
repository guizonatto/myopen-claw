"""add city segmentation and city dimension to strategy learning

Revision ID: 0009
Revises: 0008
Create Date: 2026-04-23
"""

from alembic import op
import sqlalchemy as sa


revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None
SCHEMA = "crm_mcp"


def upgrade():
    op.add_column("contatos", sa.Column("city", sa.Text(), nullable=True), schema=SCHEMA)
    op.add_column(
        "contatos",
        sa.Column("inferred_city", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        schema=SCHEMA,
    )
    op.create_index("idx_contatos_city_client_type", "contatos", ["city", "client_type"], schema=SCHEMA)

    op.add_column(
        "message_strategy_outcomes",
        sa.Column("city", sa.Text(), nullable=False, server_default="unknown"),
        schema=SCHEMA,
    )
    op.add_column(
        "message_strategy_rankings",
        sa.Column("city", sa.Text(), nullable=False, server_default="unknown"),
        schema=SCHEMA,
    )

    op.drop_index("idx_message_strategy_rankings_lookup", table_name="message_strategy_rankings", schema=SCHEMA)
    op.create_index(
        "idx_message_strategy_rankings_lookup",
        "message_strategy_rankings",
        ["stage", "client_type", "city", "region", "channel", "message_archetype"],
        schema=SCHEMA,
    )


def downgrade():
    op.drop_index("idx_message_strategy_rankings_lookup", table_name="message_strategy_rankings", schema=SCHEMA)
    op.create_index(
        "idx_message_strategy_rankings_lookup",
        "message_strategy_rankings",
        ["stage", "client_type", "region", "channel", "message_archetype"],
        schema=SCHEMA,
    )

    op.drop_column("message_strategy_rankings", "city", schema=SCHEMA)
    op.drop_column("message_strategy_outcomes", "city", schema=SCHEMA)

    op.drop_index("idx_contatos_city_client_type", table_name="contatos", schema=SCHEMA)
    op.drop_column("contatos", "inferred_city", schema=SCHEMA)
    op.drop_column("contatos", "city", schema=SCHEMA)
