-- Schema CRM (contatos, pipeline de prontidao e trilhas de interacao)
CREATE TABLE IF NOT EXISTS contatos (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    nome                    TEXT NOT NULL,
    apelido                 TEXT,
    tipo                    TEXT,
    aniversario             DATE,
    telefone                TEXT,
    whatsapp                TEXT,
    email                   TEXT,
    linkedin                TEXT,
    instagram               TEXT,
    empresa                 TEXT,
    cargo                   TEXT,
    setor                   TEXT,
    city                    TEXT,
    region                  TEXT,
    client_type             TEXT,
    inferred_city           BOOLEAN NOT NULL DEFAULT FALSE,
    inferred_region         BOOLEAN NOT NULL DEFAULT FALSE,
    inferred_client_type    BOOLEAN NOT NULL DEFAULT FALSE,
    cnpj                    TEXT,
    cnaes                   TEXT[],
    pipeline_status         TEXT,
    stage                   TEXT,
    icp_type                TEXT,
    readiness_status        TEXT DEFAULT 'ingested',
    readiness_score         INTEGER,
    verified_signals_count  INTEGER NOT NULL DEFAULT 0,
    last_enriched_at        TIMESTAMPTZ,
    fresh_until             TIMESTAMPTZ,
    needs_human_review      BOOLEAN NOT NULL DEFAULT TRUE,
    do_not_contact          BOOLEAN NOT NULL DEFAULT FALSE,
    do_not_contact_reason   TEXT,
    do_not_contact_at       TIMESTAMPTZ,
    persona_profile         TEXT,
    pain_hypothesis         TEXT,
    recent_signal           TEXT,
    offer_fit               TEXT,
    preferred_tone          TEXT,
    best_contact_window     TEXT,
    notas                   TEXT,
    ativo                   BOOLEAN DEFAULT TRUE,
    ultimo_contato          TIMESTAMPTZ,
    embedding               vector(1536)
);

CREATE INDEX IF NOT EXISTS idx_contatos_nome ON contatos (nome);
CREATE INDEX IF NOT EXISTS idx_contatos_tipo ON contatos (tipo);
CREATE INDEX IF NOT EXISTS idx_contatos_empresa ON contatos (empresa);
CREATE INDEX IF NOT EXISTS idx_contatos_pipeline_status ON contatos (pipeline_status);
CREATE INDEX IF NOT EXISTS idx_contatos_readiness_status ON contatos (readiness_status);
CREATE INDEX IF NOT EXISTS idx_contatos_do_not_contact ON contatos (do_not_contact);
CREATE INDEX IF NOT EXISTS idx_contatos_fresh_until ON contatos (fresh_until);
CREATE INDEX IF NOT EXISTS idx_contatos_region_client_type ON contatos (region, client_type);
CREATE INDEX IF NOT EXISTS idx_contatos_city_client_type ON contatos (city, client_type);
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
CREATE INDEX IF NOT EXISTS idx_rel_contato ON contato_relacionamentos (contato_id);
CREATE INDEX IF NOT EXISTS idx_rel_relacionado ON contato_relacionamentos (relacionado_id);

CREATE TABLE IF NOT EXISTS contact_enrichment_runs (
    id                          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    contato_id                  UUID NOT NULL REFERENCES contatos(id) ON DELETE CASCADE,
    mode                        TEXT NOT NULL DEFAULT 'deep',
    source                      TEXT,
    confidence                  DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    evidence                    TEXT,
    divergence_whatsapp         BOOLEAN NOT NULL DEFAULT FALSE,
    divergence_email            BOOLEAN NOT NULL DEFAULT FALSE,
    divergence_company_or_cnpj  BOOLEAN NOT NULL DEFAULT FALSE,
    notes                       TEXT
);
CREATE INDEX IF NOT EXISTS idx_enrichment_contato ON contact_enrichment_runs (contato_id);
CREATE INDEX IF NOT EXISTS idx_enrichment_created_at ON contact_enrichment_runs (created_at DESC);

CREATE TABLE IF NOT EXISTS contact_interactions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    contato_id      UUID NOT NULL REFERENCES contatos(id) ON DELETE CASCADE,
    channel         TEXT NOT NULL,
    direction       TEXT NOT NULL,
    kind            TEXT NOT NULL DEFAULT 'conversation',
    content_summary TEXT NOT NULL,
    outcome         TEXT,
    intent          TEXT,
    approved_by     TEXT,
    draft_text      TEXT,
    sent_at         TIMESTAMPTZ,
    metadata_json   TEXT
);
CREATE INDEX IF NOT EXISTS idx_interactions_contato ON contact_interactions (contato_id);
CREATE INDEX IF NOT EXISTS idx_interactions_channel ON contact_interactions (channel);
CREATE INDEX IF NOT EXISTS idx_interactions_created_at ON contact_interactions (created_at DESC);

CREATE TABLE IF NOT EXISTS contact_tasks (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    contato_id      UUID NOT NULL REFERENCES contatos(id) ON DELETE CASCADE,
    owner           TEXT,
    objective       TEXT NOT NULL,
    channel         TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'open',
    priority        TEXT NOT NULL DEFAULT 'medium',
    due_at          TIMESTAMPTZ NOT NULL,
    reminder_at     TIMESTAMPTZ,
    sla_hours       INTEGER,
    sync_calendar   BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS idx_tasks_contato ON contact_tasks (contato_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status_due ON contact_tasks (status, due_at);

CREATE TABLE IF NOT EXISTS calendar_links (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    contato_id          UUID NOT NULL REFERENCES contatos(id) ON DELETE CASCADE,
    task_id             UUID NOT NULL REFERENCES contact_tasks(id) ON DELETE CASCADE,
    provider            TEXT NOT NULL DEFAULT 'google_calendar',
    calendar_event_id   TEXT,
    sync_status         TEXT NOT NULL DEFAULT 'pending_sync',
    last_sync_at        TIMESTAMPTZ,
    sync_error          TEXT
);
CREATE INDEX IF NOT EXISTS idx_calendar_links_task ON calendar_links (task_id);
CREATE INDEX IF NOT EXISTS idx_calendar_links_status ON calendar_links (sync_status);

CREATE TABLE IF NOT EXISTS message_strategy_outcomes (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    contato_id          UUID NOT NULL REFERENCES contatos(id) ON DELETE CASCADE,
    interaction_id      UUID REFERENCES contact_interactions(id) ON DELETE SET NULL,
    stage               TEXT NOT NULL,
    client_type         TEXT NOT NULL,
    city                TEXT NOT NULL DEFAULT 'unknown',
    region              TEXT NOT NULL,
    channel             TEXT NOT NULL,
    message_archetype   TEXT NOT NULL,
    strategy_key        TEXT NOT NULL,
    outcome             TEXT NOT NULL,
    stage_hops          INTEGER NOT NULL DEFAULT 0,
    score_delta         DOUBLE PRECISION NOT NULL,
    metadata_json       TEXT
);
CREATE INDEX IF NOT EXISTS idx_message_strategy_outcomes_strategy_key ON message_strategy_outcomes (strategy_key);
CREATE INDEX IF NOT EXISTS idx_message_strategy_outcomes_created_at ON message_strategy_outcomes (created_at DESC);

CREATE TABLE IF NOT EXISTS message_strategy_rankings (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    stage                   TEXT NOT NULL,
    client_type             TEXT NOT NULL,
    city                    TEXT NOT NULL DEFAULT 'unknown',
    region                  TEXT NOT NULL,
    channel                 TEXT NOT NULL,
    message_archetype       TEXT NOT NULL,
    strategy_key            TEXT NOT NULL UNIQUE,
    attempts                INTEGER NOT NULL DEFAULT 0,
    total_outcome_points    DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    smoothed_score          DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    confidence              DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    low_confidence          BOOLEAN NOT NULL DEFAULT TRUE,
    last_outcome_at         TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_message_strategy_rankings_lookup
    ON message_strategy_rankings (stage, client_type, city, region, channel, message_archetype);

CREATE TABLE IF NOT EXISTS incoming_message_buffers (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    contato_id      UUID NOT NULL REFERENCES contatos(id) ON DELETE CASCADE,
    channel         TEXT NOT NULL DEFAULT 'whatsapp',
    status          TEXT NOT NULL DEFAULT 'open',
    flush_reason    TEXT,
    grouped_count   INTEGER NOT NULL DEFAULT 0,
    payload_json    TEXT,
    flushed_at      TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_incoming_message_buffers_lookup
    ON incoming_message_buffers (contato_id, status);

CREATE TABLE IF NOT EXISTS feedback_review_sessions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    batch_id        TEXT NOT NULL,
    stage           TEXT,
    city            TEXT,
    client_type     TEXT,
    status          TEXT NOT NULL DEFAULT 'open',
    channel         TEXT NOT NULL DEFAULT 'discord',
    thread_ref      TEXT,
    metadata_json   TEXT
);
CREATE INDEX IF NOT EXISTS idx_feedback_review_sessions_batch
    ON feedback_review_sessions (batch_id, status);

CREATE TABLE IF NOT EXISTS feedback_review_entries (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    session_id      UUID NOT NULL REFERENCES feedback_review_sessions(id) ON DELETE CASCADE,
    author          TEXT NOT NULL DEFAULT 'sales_reviewer',
    feedback_text   TEXT NOT NULL,
    tags_json       TEXT,
    metadata_json   TEXT
);
CREATE INDEX IF NOT EXISTS idx_feedback_review_entries_session
    ON feedback_review_entries (session_id, created_at);

CREATE TABLE IF NOT EXISTS strategy_update_proposals (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    session_id          UUID NOT NULL REFERENCES feedback_review_sessions(id) ON DELETE CASCADE,
    proposal_batch_id   TEXT NOT NULL UNIQUE,
    status              TEXT NOT NULL DEFAULT 'draft_review',
    proposed_by         TEXT,
    approved_by         TEXT,
    rejected_reason     TEXT,
    proposal_json       TEXT NOT NULL,
    decision_notes      TEXT
);
CREATE INDEX IF NOT EXISTS idx_strategy_update_proposals_status
    ON strategy_update_proposals (status, created_at);

CREATE TABLE IF NOT EXISTS operation_audit_logs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actor           TEXT NOT NULL DEFAULT 'system',
    role            TEXT NOT NULL DEFAULT 'system',
    operation       TEXT NOT NULL,
    resource_id     TEXT,
    status          TEXT NOT NULL,
    reason          TEXT,
    before_json     TEXT,
    after_json      TEXT,
    error           TEXT
);
CREATE INDEX IF NOT EXISTS idx_operation_audit_logs_lookup
    ON operation_audit_logs (operation, status, created_at);
