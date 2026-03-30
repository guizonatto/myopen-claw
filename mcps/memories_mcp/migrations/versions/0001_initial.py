"""
Initial migration for memories table
"""

# AS VARIÁVEIS OBRIGATÓRIAS DO ALEMBIC
revision = '0001'
down_revision = None
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
import sqlalchemy.dialects.postgresql as pg

def upgrade():
    op.execute('CREATE SCHEMA IF NOT EXISTS memories_mcp')
    op.create_table(
        'memories',
        sa.Column('id', pg.UUID(as_uuid=True), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('contato_id', pg.UUID(as_uuid=True), nullable=True),
        sa.Column('entidade', sa.Text(), nullable=True),
        sa.Column('tipo', sa.Text(), nullable=False, server_default='semantica'),
        sa.Column('categoria', sa.Text(), nullable=True),
        sa.Column('conteudo', sa.Text(), nullable=False),
        sa.Column('embedding', sa.Text(), nullable=True),
        sa.Column('importancia', sa.SmallInteger(), server_default='3'),
        sa.Column('validade', sa.DateTime(timezone=True), nullable=True),
        sa.Column('recorrencia', sa.Text(), nullable=True),
        sa.Column('dia_mes', sa.SmallInteger(), nullable=True),
        sa.Column('mes', sa.SmallInteger(), nullable=True),
        sa.Column('acessos', sa.Integer(), server_default='0'),
        sa.Column('ultimo_acesso', sa.DateTime(timezone=True), nullable=True),
        sa.Column('origem', sa.Text(), nullable=True),
        schema='memories_mcp',
    )
    op.create_index('idx_memories_contato_id', 'memories', ['contato_id'], postgresql_where=sa.text('contato_id IS NOT NULL'), schema='memories_mcp')
    op.create_index('idx_memories_tipo', 'memories', ['tipo'], schema='memories_mcp')
    op.create_index('idx_memories_entidade', 'memories', ['entidade'], schema='memories_mcp')
    op.create_index('idx_memories_categoria', 'memories', ['categoria'], schema='memories_mcp')
    op.create_index('idx_memories_recorrencia', 'memories', ['recorrencia', 'mes', 'dia_mes'], postgresql_where=sa.text('recorrencia IS NOT NULL'), schema='memories_mcp')
    op.create_index('idx_memories_validade', 'memories', ['validade'], postgresql_where=sa.text('validade IS NOT NULL'), schema='memories_mcp')
    # O índice vector/pgvector precisa ser criado manualmente após a migration

def downgrade():
    op.drop_index('idx_memories_validade', table_name='memories', schema='memories_mcp')
    op.drop_index('idx_memories_recorrencia', table_name='memories', schema='memories_mcp')
    op.drop_index('idx_memories_categoria', table_name='memories', schema='memories_mcp')
    op.drop_index('idx_memories_entidade', table_name='memories', schema='memories_mcp')
    op.drop_index('idx_memories_tipo', table_name='memories', schema='memories_mcp')
    op.drop_index('idx_memories_contato_id', table_name='memories', schema='memories_mcp')
    op.drop_table('memories', schema='memories_mcp')
