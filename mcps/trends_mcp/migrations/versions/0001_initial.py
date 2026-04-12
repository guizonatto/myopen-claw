"""
Initial migration for trends table
"""

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa

def upgrade():
    op.execute('CREATE SCHEMA IF NOT EXISTS trends_mcp')
    op.create_table(
        'trends',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('nome', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        schema='trends_mcp'
    )
    op.create_index('ix_trends_id', 'trends', ['id'], unique=False, schema='trends_mcp')
    op.create_index('ix_trends_nome', 'trends', ['nome'], unique=False, schema='trends_mcp')

def downgrade():
    op.drop_table('trends', schema='trends_mcp')
