-- Schema CRM (contatos e relacionamentos)
CREATE TABLE IF NOT EXISTS contatos (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    nome        TEXT NOT NULL,
    apelido     TEXT,
    tipo        TEXT,
    aniversario DATE,
    telefone    TEXT,
    whatsapp    TEXT,
    email       TEXT,
    linkedin    TEXT,
    instagram   TEXT,
    empresa     TEXT,
    cargo       TEXT,
    setor       TEXT,
    notas       TEXT,
    ativo           BOOLEAN DEFAULT TRUE,
    ultimo_contato  TIMESTAMPTZ,
    embedding   vector(1536)
);

CREATE INDEX IF NOT EXISTS idx_contatos_nome    ON contatos (nome);
CREATE INDEX IF NOT EXISTS idx_contatos_tipo    ON contatos (tipo);
CREATE INDEX IF NOT EXISTS idx_contatos_empresa ON contatos (empresa);
CREATE INDEX IF NOT EXISTS idx_contatos_aniversario
    ON contatos (EXTRACT(MONTH FROM aniversario), EXTRACT(DAY FROM aniversario))
    WHERE aniversario IS NOT NULL;

CREATE TABLE IF NOT EXISTS contato_relacionamentos (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    contato_id      UUID NOT NULL REFERENCES contatos(id) ON DELETE CASCADE,
    relacionado_id  UUID NOT NULL REFERENCES contatos(id) ON DELETE CASCADE,
    tipo            TEXT NOT NULL,
    notas           TEXT,
    UNIQUE (contato_id, relacionado_id, tipo)
);
CREATE INDEX IF NOT EXISTS idx_rel_contato     ON contato_relacionamentos (contato_id);
CREATE INDEX IF NOT EXISTS idx_rel_relacionado ON contato_relacionamentos (relacionado_id);
