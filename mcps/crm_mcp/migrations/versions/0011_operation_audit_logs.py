"""add operation audit logs table

Revision ID: 0011
Revises: 0010
Create Date: 2026-04-25
"""

from alembic import op
import sqlalchemy as sa
import sqlalchemy.dialects.postgresql as pg


revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None
SCHEMA = "crm_mcp"


def upgrade():
    op.create_table(
        "operation_audit_logs",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("actor", sa.Text(), nullable=False, server_default="system"),
        sa.Column("role", sa.Text(), nullable=False, server_default="system"),
        sa.Column("operation", sa.Text(), nullable=False),
        sa.Column("resource_id", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("before_json", sa.Text(), nullable=True),
        sa.Column("after_json", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        schema=SCHEMA,
    )
    op.create_index(
        "idx_operation_audit_logs_lookup",
        "operation_audit_logs",
        ["operation", "status", "created_at"],
        schema=SCHEMA,
    )


def downgrade():
    op.drop_index("idx_operation_audit_logs_lookup", table_name="operation_audit_logs", schema=SCHEMA)
    op.drop_table("operation_audit_logs", schema=SCHEMA)
