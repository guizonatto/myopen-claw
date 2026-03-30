"""
Converte coluna embedding de Text para vector(1536) via pgvector
"""

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


def upgrade():
    # CREATE SCHEMA e CREATE EXTENSION são gerenciados pelo env.py em AUTOCOMMIT
    op.alter_column(
        'memories',
        'embedding',
        type_=Vector(1536),
        postgresql_using='NULL::vector(1536)',
        schema='memories_mcp',
    )
    op.create_index(
        'idx_memories_embedding',
        'memories',
        ['embedding'],
        postgresql_using='ivfflat',
        postgresql_with={'lists': 100},
        postgresql_ops={'embedding': 'vector_cosine_ops'},
        postgresql_where=sa.text('embedding IS NOT NULL'),
        schema='memories_mcp',
    )


def downgrade():
    op.drop_index('idx_memories_embedding', table_name='memories', schema='memories_mcp')
    op.alter_column(
        'memories',
        'embedding',
        type_=sa.Text(),
        postgresql_using='NULL::text',
        schema='memories_mcp',
    )
