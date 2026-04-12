"""add stage and icp_type to contatos

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-11
"""
from alembic import op
import sqlalchemy as sa

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'contatos',
        sa.Column('stage', sa.Text(), nullable=True),
        schema='crm_mcp',
    )
    op.add_column(
        'contatos',
        sa.Column('icp_type', sa.Text(), nullable=True),
        schema='crm_mcp',
    )


def downgrade():
    op.drop_column('contatos', 'icp_type', schema='crm_mcp')
    op.drop_column('contatos', 'stage', schema='crm_mcp')
