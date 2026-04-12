"""
Atualiza default das colunas created_at e updated_at para now() nas tabelas do CRM
"""

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa

def upgrade():
    op.alter_column(
        'contatos',
        'created_at',
        server_default=sa.text('now()'),
        schema='crm_mcp',
    )
    op.alter_column(
        'contatos',
        'updated_at',
        server_default=sa.text('now()'),
        schema='crm_mcp',
    )
    op.alter_column(
        'contato_relacionamentos',
        'created_at',
        server_default=sa.text('now()'),
        schema='crm_mcp',
    )

def downgrade():
    op.alter_column(
        'contatos',
        'created_at',
        server_default=None,
        schema='crm_mcp',
    )
    op.alter_column(
        'contatos',
        'updated_at',
        server_default=None,
        schema='crm_mcp',
    )
    op.alter_column(
        'contato_relacionamentos',
        'created_at',
        server_default=None,
        schema='crm_mcp',
    )
