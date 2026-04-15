"""change embedding vector dim from 1536 to 2560 for qwen3-embedding:4b

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-13
"""

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None

from alembic import op


def upgrade():
    # Nullify existing embeddings — incompatible dimension (1536 → 2560)
    op.execute("UPDATE memories_mcp.memories SET embedding = NULL WHERE embedding IS NOT NULL")
    op.execute("ALTER TABLE memories_mcp.memories ALTER COLUMN embedding TYPE vector(2560)")
    op.execute("DROP INDEX IF EXISTS memories_mcp.ix_memories_embedding")
    op.execute(
        "CREATE INDEX ix_memories_embedding ON memories_mcp.memories "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50)"
    )


def downgrade():
    op.execute("UPDATE memories_mcp.memories SET embedding = NULL WHERE embedding IS NOT NULL")
    op.execute("ALTER TABLE memories_mcp.memories ALTER COLUMN embedding TYPE vector(1536)")
    op.execute("DROP INDEX IF EXISTS memories_mcp.ix_memories_embedding")
    op.execute(
        "CREATE INDEX ix_memories_embedding ON memories_mcp.memories "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50)"
    )
