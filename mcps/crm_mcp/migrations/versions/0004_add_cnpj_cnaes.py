"""add cnpj and cnaes to contatos

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-08
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'contatos',
        sa.Column('cnpj', sa.Text(), nullable=True),
        schema='crm_mcp',
    )
    op.add_column(
        'contatos',
        sa.Column('cnaes', postgresql.ARRAY(sa.Text()), nullable=True),
        schema='crm_mcp',
    )


def downgrade():
    op.drop_column('contatos', 'cnaes', schema='crm_mcp')
    op.drop_column('contatos', 'cnpj', schema='crm_mcp')
