"""
Atualiza default das colunas created_at e updated_at para now()
"""

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa

def upgrade():
    op.alter_column(
        'memories',
        'created_at',
        server_default=sa.text('now()'),
        schema='memories_mcp',
    )
    op.alter_column(
        'memories',
        'updated_at',
        server_default=sa.text('now()'),
        schema='memories_mcp',
    )

def downgrade():
    op.alter_column(
        'memories',
        'created_at',
        server_default=None,
        schema='memories_mcp',
    )
    op.alter_column(
        'memories',
        'updated_at',
        server_default=None,
        schema='memories_mcp',
    )
