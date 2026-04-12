"""add pipeline_status to contatos

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-11
"""
from alembic import op
import sqlalchemy as sa

revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'contatos',
        sa.Column('pipeline_status', sa.Text(), nullable=True),
        schema='crm_mcp',
    )


def downgrade():
    op.drop_column('contatos', 'pipeline_status', schema='crm_mcp')
