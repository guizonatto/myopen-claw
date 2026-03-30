"""
Initial migration for contatos e contato_relacionamentos
"""

# AS VARIÁVEIS OBRIGATÓRIAS DO ALEMBIC
revision = '0001'
down_revision = None
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
import sqlalchemy.dialects.postgresql as pg

SCHEMA = 'crm_mcp'


def upgrade():
    op.execute(f'CREATE SCHEMA IF NOT EXISTS {SCHEMA}')

    op.create_table(
        'contatos',
        sa.Column('id', pg.UUID(as_uuid=True), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('nome', sa.Text(), nullable=False),
        sa.Column('apelido', sa.Text(), nullable=True),
        sa.Column('tipo', sa.Text(), nullable=True),
        sa.Column('aniversario', sa.DateTime(), nullable=True),
        sa.Column('telefone', sa.Text(), nullable=True),
        sa.Column('whatsapp', sa.Text(), nullable=True),
        sa.Column('email', sa.Text(), nullable=True),
        sa.Column('linkedin', sa.Text(), nullable=True),
        sa.Column('instagram', sa.Text(), nullable=True),
        sa.Column('empresa', sa.Text(), nullable=True),
        sa.Column('cargo', sa.Text(), nullable=True),
        sa.Column('setor', sa.Text(), nullable=True),
        sa.Column('notas', sa.Text(), nullable=True),
        sa.Column('ativo', sa.Boolean(), server_default=sa.text('true')),
        sa.Column('ultimo_contato', sa.DateTime(timezone=True), nullable=True),
        sa.Column('embedding', sa.Text(), nullable=True),
        schema=SCHEMA,
    )
    op.create_index('idx_contatos_nome', 'contatos', ['nome'], schema=SCHEMA)
    op.create_index('idx_contatos_tipo', 'contatos', ['tipo'], schema=SCHEMA)
    op.create_index('idx_contatos_empresa', 'contatos', ['empresa'], schema=SCHEMA)
    op.create_index(
        'idx_contatos_aniversario',
        'contatos',
        [sa.text('EXTRACT(MONTH FROM aniversario)'), sa.text('EXTRACT(DAY FROM aniversario)')],
        postgresql_where=sa.text('aniversario IS NOT NULL'),
        schema=SCHEMA,
    )

    op.create_table(
        'contato_relacionamentos',
        sa.Column('id', pg.UUID(as_uuid=True), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('contato_id', pg.UUID(as_uuid=True), sa.ForeignKey(f'{SCHEMA}.contatos.id', ondelete='CASCADE'), nullable=False),
        sa.Column('relacionado_id', pg.UUID(as_uuid=True), sa.ForeignKey(f'{SCHEMA}.contatos.id', ondelete='CASCADE'), nullable=False),
        sa.Column('tipo', sa.Text(), nullable=False),
        sa.Column('notas', sa.Text(), nullable=True),
        schema=SCHEMA,
    )
    op.create_index('idx_rel_contato', 'contato_relacionamentos', ['contato_id'], schema=SCHEMA)
    op.create_index('idx_rel_relacionado', 'contato_relacionamentos', ['relacionado_id'], schema=SCHEMA)


def downgrade():
    op.drop_index('idx_rel_relacionado', table_name='contato_relacionamentos', schema=SCHEMA)
    op.drop_index('idx_rel_contato', table_name='contato_relacionamentos', schema=SCHEMA)
    op.drop_table('contato_relacionamentos', schema=SCHEMA)
    op.drop_index('idx_contatos_aniversario', table_name='contatos', schema=SCHEMA)
    op.drop_index('idx_contatos_empresa', table_name='contatos', schema=SCHEMA)
    op.drop_index('idx_contatos_tipo', table_name='contatos', schema=SCHEMA)
    op.drop_index('idx_contatos_nome', table_name='contatos', schema=SCHEMA)
    op.drop_table('contatos', schema=SCHEMA)
    op.execute(f'DROP SCHEMA IF EXISTS {SCHEMA}')
