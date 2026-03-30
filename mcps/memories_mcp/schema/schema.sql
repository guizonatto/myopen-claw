-- Schema Memórias
CREATE TABLE IF NOT EXISTS memories (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    contato_id  UUID,
    entidade    TEXT,
    tipo        TEXT NOT NULL DEFAULT 'semantica',
    categoria   TEXT,
    conteudo    TEXT NOT NULL,
    embedding   vector(1536),
    importancia SMALLINT DEFAULT 3 CHECK (importancia BETWEEN 1 AND 5),
    validade    TIMESTAMPTZ,
    recorrencia TEXT CHECK (recorrencia IN ('anual', 'mensal', 'semanal')),
    dia_mes     SMALLINT CHECK (dia_mes BETWEEN 1 AND 31),
    mes         SMALLINT CHECK (mes BETWEEN 1 AND 12),
    acessos       INTEGER DEFAULT 0,
    ultimo_acesso TIMESTAMPTZ,
    origem  TEXT
);
CREATE INDEX IF NOT EXISTS idx_memories_contato_id ON memories (contato_id)
    WHERE contato_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_memories_tipo       ON memories (tipo);
CREATE INDEX IF NOT EXISTS idx_memories_entidade   ON memories (entidade);
CREATE INDEX IF NOT EXISTS idx_memories_categoria  ON memories (categoria);
CREATE INDEX IF NOT EXISTS idx_memories_recorrencia
    ON memories (recorrencia, mes, dia_mes)
    WHERE recorrencia IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_memories_validade   ON memories (validade)
    WHERE validade IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_memories_embedding
    ON memories USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50)
    WHERE embedding IS NOT NULL;
