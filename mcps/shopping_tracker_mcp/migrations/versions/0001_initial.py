"""
Initial migration — compras and wishlist tables
"""

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.execute('CREATE SCHEMA IF NOT EXISTS shopping_tracker_mcp')    
    op.create_table(
        'compras',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('nome', sa.String(), nullable=True),
        sa.Column('quantidade', sa.Float(), nullable=True),
        sa.Column('unidade', sa.String(), nullable=True, server_default='unidade'),
        sa.Column('wishlist', sa.Boolean(), nullable=True, server_default=sa.text('false')),
        sa.Column('ultima_compra', sa.Date(), nullable=True),
        sa.Column('preco', sa.Float(), nullable=True),
        sa.Column('loja', sa.String(), nullable=True),
        sa.Column('marca', sa.String(), nullable=True),
        sa.Column('volume_embalagem', sa.String(), nullable=True),
        schema='shopping_tracker_mcp'
    )
    op.create_index('ix_compras_id', 'compras', ['id'], unique=False, schema='shopping_tracker_mcp')
    op.create_index('ix_compras_nome', 'compras', ['nome'], unique=False, schema='shopping_tracker_mcp')

    op.create_table(
        'wishlist',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('nome', sa.String(), nullable=True),
        sa.Column('quantidade', sa.Float(), nullable=True),
        sa.Column('unidade', sa.String(), nullable=True, server_default='unidade'),
        sa.Column('wishlist', sa.Boolean(), nullable=True, server_default=sa.text('true')),
        sa.Column('preco', sa.Float(), nullable=True),
        sa.Column('loja', sa.String(), nullable=True),
        sa.Column('marca', sa.String(), nullable=True),
        sa.Column('volume_embalagem', sa.String(), nullable=True),
        schema='shopping_tracker_mcp'
    )
    op.create_index('ix_wishlist_id', 'wishlist', ['id'], unique=False, schema='shopping_tracker_mcp')
    op.create_index('ix_wishlist_nome', 'wishlist', ['nome'], unique=False, schema='shopping_tracker_mcp')


def downgrade():
    op.drop_index('ix_wishlist_nome', table_name='wishlist', schema='shopping_tracker_mcp')
    op.drop_index('ix_wishlist_id', table_name='wishlist', schema='shopping_tracker_mcp')
    op.drop_table('wishlist', schema='shopping_tracker_mcp')
    op.drop_index('ix_compras_nome', table_name='compras', schema='shopping_tracker_mcp')
    op.drop_index('ix_compras_id', table_name='compras', schema='shopping_tracker_mcp')
    op.drop_table('compras', schema='shopping_tracker_mcp')
    op.execute('DROP SCHEMA IF EXISTS shopping_tracker_mcp CASCADE')
