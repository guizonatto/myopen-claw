"""
Tool: storage
Função: Persiste eventos brutos de uso de LLM em SQLite (rate buckets/limits) e PostgreSQL (usage_events).
Usar quando: Precisar registrar tentativas por service/provider/model e consolidar relatórios.

ENV_VARS:
  - MODEL_USAGE_POSTGRES_URL: PostgreSQL DSN para usage_events (opcional; fallback: SQLite)
  - MODEL_USAGE_REDIS_URL: Redis URL para rate-limit buckets (opcional; fallback: SQLite)

DB_TABLES:
  - usage_events: leitura+escrita (PostgreSQL quando configurado, senão SQLite)
  - report_dispatches: leitura+escrita (SQLite)
  - model_limits: leitura+escrita (SQLite)
  - model_rate_buckets: leitura+escrita (SQLite)
"""
from dataclasses import dataclass
from datetime import datetime
import logging
import sqlite3
from pathlib import Path
from typing import Any

from llm_usage_telemetry.reporting import UsageSummaryRow

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class UsageEvent:
    timestamp: datetime
    service: str
    provider: str
    model: str
    request_kind: str
    success: bool
    http_status: int | None
    latency_ms: int | None
    attempt_number: int
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    token_accuracy: str
    input_chars: int | None = None
    input_words: int | None = None
    input_estimated_tokens: int | None = None
    response_chars: int | None = None
    response_words: int | None = None
    response_estimated_tokens: int | None = None
    request_payload: str | None = None
    response_payload: str | None = None
    origin_type: str | None = None
    origin_name: str | None = None
    trigger_type: str | None = None
    trigger_name: str | None = None
    agent_name: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    request_id: str | None = None
    logical_request_id: str | None = None


@dataclass(slots=True)
class ModelLimits:
    provider: str
    model: str
    enabled: bool
    disabled_reason: str | None
    context_window: int | None
    max_output_tokens: int | None
    rpm: int | None
    rpd: int | None
    tpm: int | None
    tpd: int | None
    updated_at: datetime | None = None


def connect_db(db_path: str | Path) -> sqlite3.Connection:
    if str(db_path) == ":memory:":
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        return conn
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def initialize_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS usage_events (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          timestamp TEXT NOT NULL,
          service TEXT NOT NULL,
          provider TEXT NOT NULL,
          model TEXT NOT NULL,
          request_kind TEXT NOT NULL,
          success INTEGER NOT NULL,
          http_status INTEGER,
          latency_ms INTEGER,
          attempt_number INTEGER NOT NULL,
          input_tokens INTEGER,
          output_tokens INTEGER,
          total_tokens INTEGER,
          token_accuracy TEXT NOT NULL,
          input_chars INTEGER,
          input_words INTEGER,
          input_estimated_tokens INTEGER,
          response_chars INTEGER,
          response_words INTEGER,
          response_estimated_tokens INTEGER,
          request_payload TEXT,
          response_payload TEXT,
          origin_type TEXT,
          origin_name TEXT,
          trigger_type TEXT,
          trigger_name TEXT,
          agent_name TEXT,
          error_code TEXT,
          error_message TEXT,
          request_id TEXT,
          logical_request_id TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_usage_events_window
          ON usage_events (timestamp, service, provider, model, request_kind);

        CREATE TABLE IF NOT EXISTS report_dispatches (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          report_key TEXT NOT NULL,
          bucket_start TEXT NOT NULL,
          channel TEXT NOT NULL,
          target TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(report_key, bucket_start, channel, target)
        );

        CREATE TABLE IF NOT EXISTS model_limits (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          provider TEXT NOT NULL,
          model TEXT NOT NULL,
          enabled INTEGER NOT NULL DEFAULT 1,
          disabled_reason TEXT,
          context_window INTEGER,
          max_output_tokens INTEGER,
          rpm INTEGER,
          rpd INTEGER,
          tpm INTEGER,
          tpd INTEGER,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(provider, model)
        );

        CREATE TABLE IF NOT EXISTS model_rate_buckets (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          provider TEXT NOT NULL,
          model TEXT NOT NULL,
          bucket_kind TEXT NOT NULL, -- minute|day
          bucket_start TEXT NOT NULL,
          requests INTEGER NOT NULL DEFAULT 0,
          tokens INTEGER NOT NULL DEFAULT 0,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(provider, model, bucket_kind, bucket_start)
        );
        """
    )
    existing_columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(usage_events)").fetchall()
    }
    for column_name, column_type in (
        ("origin_type", "TEXT"),
        ("origin_name", "TEXT"),
        ("trigger_type", "TEXT"),
        ("trigger_name", "TEXT"),
        ("agent_name", "TEXT"),
        ("input_chars", "INTEGER"),
        ("input_words", "INTEGER"),
        ("input_estimated_tokens", "INTEGER"),
        ("response_chars", "INTEGER"),
        ("response_words", "INTEGER"),
        ("response_estimated_tokens", "INTEGER"),
        ("request_payload", "TEXT"),
        ("response_payload", "TEXT"),
    ):
        if column_name not in existing_columns:
            conn.execute(f"ALTER TABLE usage_events ADD COLUMN {column_name} {column_type}")
    conn.commit()


def get_model_limits(conn: sqlite3.Connection, provider: str, model: str) -> ModelLimits | None:
    row = conn.execute(
        """
        SELECT
          provider,
          model,
          enabled,
          disabled_reason,
          context_window,
          max_output_tokens,
          rpm,
          rpd,
          tpm,
          tpd,
          updated_at
        FROM model_limits
        WHERE provider = ? AND model = ?
        """,
        (provider, model),
    ).fetchone()
    if not row:
        return None
    updated_at = None
    if row["updated_at"]:
        try:
            updated_at = datetime.fromisoformat(row["updated_at"])
        except Exception:
            updated_at = None
    return ModelLimits(
        provider=row["provider"],
        model=row["model"],
        enabled=bool(row["enabled"]),
        disabled_reason=row["disabled_reason"],
        context_window=row["context_window"],
        max_output_tokens=row["max_output_tokens"],
        rpm=row["rpm"],
        rpd=row["rpd"],
        tpm=row["tpm"],
        tpd=row["tpd"],
        updated_at=updated_at,
    )


def upsert_model_limits(
    conn: sqlite3.Connection,
    provider: str,
    model: str,
    *,
    enabled: bool | None = None,
    disabled_reason: str | None = None,
    context_window: int | None = None,
    max_output_tokens: int | None = None,
    rpm: int | None = None,
    rpd: int | None = None,
    tpm: int | None = None,
    tpd: int | None = None,
) -> None:
    existing = get_model_limits(conn, provider, model)
    if existing is None:
        conn.execute(
            """
            INSERT INTO model_limits (
              provider, model, enabled, disabled_reason,
              context_window, max_output_tokens, rpm, rpd, tpm, tpd
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                provider,
                model,
                int(True if enabled is None else enabled),
                disabled_reason,
                context_window,
                max_output_tokens,
                rpm,
                rpd,
                tpm,
                tpd,
            ),
        )
        conn.commit()
        return

    conn.execute(
        """
        UPDATE model_limits
        SET
          enabled = ?,
          disabled_reason = ?,
          context_window = ?,
          max_output_tokens = ?,
          rpm = ?,
          rpd = ?,
          tpm = ?,
          tpd = ?,
          updated_at = CURRENT_TIMESTAMP
        WHERE provider = ? AND model = ?
        """,
        (
            int(existing.enabled if enabled is None else enabled),
            existing.disabled_reason if disabled_reason is None else disabled_reason,
            existing.context_window if context_window is None else context_window,
            existing.max_output_tokens if max_output_tokens is None else max_output_tokens,
            existing.rpm if rpm is None else rpm,
            existing.rpd if rpd is None else rpd,
            existing.tpm if tpm is None else tpm,
            existing.tpd if tpd is None else tpd,
            provider,
            model,
        ),
    )
    conn.commit()


def record_usage_event(conn: sqlite3.Connection, event: UsageEvent) -> None:
    import time as _time
    params = (
        event.timestamp.isoformat(),
        event.service,
        event.provider,
        event.model,
        event.request_kind,
        int(event.success),
        event.http_status,
        event.latency_ms,
        event.attempt_number,
        event.input_tokens,
        event.output_tokens,
        event.total_tokens,
        event.token_accuracy,
        event.input_chars,
        event.input_words,
        event.input_estimated_tokens,
        event.response_chars,
        event.response_words,
        event.response_estimated_tokens,
        event.request_payload,
        event.response_payload,
        event.origin_type,
        event.origin_name,
        event.trigger_type,
        event.trigger_name,
        event.agent_name,
        event.error_code,
        event.error_message,
        event.request_id,
        event.logical_request_id,
    )
    sql = """
        INSERT INTO usage_events (
          timestamp, service, provider, model, request_kind, success,
          http_status, latency_ms, attempt_number,
          input_tokens, output_tokens, total_tokens, token_accuracy,
          input_chars, input_words, input_estimated_tokens,
          response_chars, response_words, response_estimated_tokens,
          request_payload, response_payload,
          origin_type, origin_name, trigger_type, trigger_name, agent_name,
          error_code, error_message, request_id, logical_request_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    for _attempt in range(3):
        try:
            conn.execute(sql, params)
            conn.commit()
            return
        except sqlite3.OperationalError as exc:
            if "locked" in str(exc) and _attempt < 2:
                _time.sleep(0.1 * (_attempt + 1))
                continue
            raise


# ---------------------------------------------------------------------------
# PostgreSQL support — full migration (usage_events + rate_buckets + model_limits + dispatches)
# ---------------------------------------------------------------------------

_PG_CREATE_ALL = """
CREATE TABLE IF NOT EXISTS llm_model_limits (
  id          BIGSERIAL PRIMARY KEY,
  provider    TEXT NOT NULL,
  model       TEXT NOT NULL,
  enabled     BOOLEAN NOT NULL DEFAULT TRUE,
  disabled_reason TEXT,
  context_window  INTEGER,
  max_output_tokens INTEGER,
  rpm  INTEGER,
  rpd  INTEGER,
  tpm  INTEGER,
  tpd  INTEGER,
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(provider, model)
);

CREATE TABLE IF NOT EXISTS llm_model_rate_buckets (
  id          BIGSERIAL PRIMARY KEY,
  provider    TEXT NOT NULL,
  model       TEXT NOT NULL,
  bucket_kind TEXT NOT NULL,
  bucket_start TEXT NOT NULL,
  requests    INTEGER NOT NULL DEFAULT 0,
  tokens      INTEGER NOT NULL DEFAULT 0,
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(provider, model, bucket_kind, bucket_start)
);
CREATE INDEX IF NOT EXISTS idx_llm_rate_buckets_lookup
  ON llm_model_rate_buckets (provider, model, bucket_kind, bucket_start);

CREATE TABLE IF NOT EXISTS llm_report_dispatches (
  id          BIGSERIAL PRIMARY KEY,
  report_key  TEXT NOT NULL,
  bucket_start TEXT NOT NULL,
  channel     TEXT NOT NULL,
  target      TEXT NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(report_key, bucket_start, channel, target)
);
"""

_PG_CREATE_USAGE_EVENTS = """
CREATE TABLE IF NOT EXISTS llm_usage_events (
  id          BIGSERIAL PRIMARY KEY,
  timestamp   TIMESTAMPTZ NOT NULL,
  service     TEXT NOT NULL,
  provider    TEXT NOT NULL,
  model       TEXT NOT NULL,
  request_kind TEXT NOT NULL,
  success     BOOLEAN NOT NULL,
  http_status SMALLINT,
  latency_ms  INTEGER,
  attempt_number SMALLINT NOT NULL,
  input_tokens    INTEGER,
  output_tokens   INTEGER,
  total_tokens    INTEGER,
  token_accuracy  TEXT NOT NULL,
  input_chars  INTEGER,
  input_words  INTEGER,
  input_estimated_tokens INTEGER,
  response_chars INTEGER,
  response_words INTEGER,
  response_estimated_tokens INTEGER,
  request_payload  TEXT,
  response_payload TEXT,
  origin_type  TEXT,
  origin_name  TEXT,
  trigger_type TEXT,
  trigger_name TEXT,
  agent_name   TEXT,
  error_code   TEXT,
  error_message TEXT,
  request_id   TEXT,
  logical_request_id TEXT
);
CREATE INDEX IF NOT EXISTS idx_llm_usage_events_ts_provider
  ON llm_usage_events (timestamp, provider, model);
"""

_PG_INSERT_USAGE_EVENT = """
INSERT INTO llm_usage_events (
  timestamp, service, provider, model, request_kind, success,
  http_status, latency_ms, attempt_number,
  input_tokens, output_tokens, total_tokens, token_accuracy,
  input_chars, input_words, input_estimated_tokens,
  response_chars, response_words, response_estimated_tokens,
  request_payload, response_payload,
  origin_type, origin_name, trigger_type, trigger_name, agent_name,
  error_code, error_message, request_id, logical_request_id
) VALUES (
  %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
  %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
)
"""


def connect_pg(pg_url: str) -> Any:
    """Return a psycopg2 connection or None if psycopg2 unavailable."""
    try:
        import psycopg2
        conn = psycopg2.connect(pg_url)
        conn.autocommit = False
        return conn
    except Exception as exc:
        logger.error("pg connect failed: %s", exc)
        return None


def ensure_pg_conn(pg_conn: Any, pg_url: str) -> Any:
    """Return a live connection, reconnecting if closed."""
    if pg_conn is None:
        return connect_pg(pg_url)
    try:
        import psycopg2
        if pg_conn.closed:
            return connect_pg(pg_url)
        # ping
        with pg_conn.cursor() as cur:
            cur.execute("SELECT 1")
        return pg_conn
    except Exception:
        try:
            pg_conn.close()
        except Exception:
            pass
        return connect_pg(pg_url)


def initialize_pg_schema(pg_conn: Any) -> None:
    with pg_conn.cursor() as cur:
        cur.execute(_PG_CREATE_USAGE_EVENTS)
    pg_conn.commit()


def record_usage_event_pg(pg_conn: Any, event: UsageEvent) -> None:
    params = (
        event.timestamp.isoformat(),
        event.service,
        event.provider,
        event.model,
        event.request_kind,
        event.success,
        event.http_status,
        event.latency_ms,
        event.attempt_number,
        event.input_tokens,
        event.output_tokens,
        event.total_tokens,
        event.token_accuracy,
        event.input_chars,
        event.input_words,
        event.input_estimated_tokens,
        event.response_chars,
        event.response_words,
        event.response_estimated_tokens,
        event.request_payload,
        event.response_payload,
        event.origin_type,
        event.origin_name,
        event.trigger_type,
        event.trigger_name,
        event.agent_name,
        event.error_code,
        event.error_message,
        event.request_id,
        event.logical_request_id,
    )
    try:
        with pg_conn.cursor() as cur:
            cur.execute(_PG_INSERT_USAGE_EVENT, params)
        pg_conn.commit()
    except Exception as exc:
        logger.error("pg record_usage_event failed: %s", exc)
        try:
            pg_conn.rollback()
        except Exception:
            pass
        raise


def initialize_pg_schema_full(pg_conn: Any) -> None:
    """Create all 4 tables in PostgreSQL (idempotent)."""
    with pg_conn.cursor() as cur:
        cur.execute(_PG_CREATE_ALL)
        cur.execute(_PG_CREATE_USAGE_EVENTS)
    pg_conn.commit()


def get_model_limits_pg(pg_conn: Any, provider: str, model: str) -> "ModelLimits | None":
    try:
        with pg_conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM llm_model_limits WHERE provider=%s AND model=%s",
                (provider, model),
            )
            row = cur.fetchone()
        if not row:
            return None
        cols = [d[0] for d in cur.description] if hasattr(cur, "description") else []
        r = dict(zip(cols, row))
        return ModelLimits(
            provider=r["provider"],
            model=r["model"],
            enabled=bool(r["enabled"]),
            disabled_reason=r.get("disabled_reason"),
            context_window=r.get("context_window"),
            max_output_tokens=r.get("max_output_tokens"),
            rpm=r.get("rpm"),
            rpd=r.get("rpd"),
            tpm=r.get("tpm"),
            tpd=r.get("tpd"),
            updated_at=r.get("updated_at"),
        )
    except Exception as exc:
        logger.error("pg get_model_limits failed: %s", exc)
        return None


def upsert_model_limits_pg(pg_conn: Any, limits: "ModelLimits") -> None:
    try:
        with pg_conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO llm_model_limits
                  (provider, model, enabled, disabled_reason, context_window,
                   max_output_tokens, rpm, rpd, tpm, tpd, updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())
                ON CONFLICT (provider, model) DO UPDATE SET
                  enabled          = EXCLUDED.enabled,
                  disabled_reason  = EXCLUDED.disabled_reason,
                  context_window   = EXCLUDED.context_window,
                  max_output_tokens= EXCLUDED.max_output_tokens,
                  rpm = EXCLUDED.rpm, rpd = EXCLUDED.rpd,
                  tpm = EXCLUDED.tpm, tpd = EXCLUDED.tpd,
                  updated_at = NOW()
                """,
                (limits.provider, limits.model, limits.enabled, limits.disabled_reason,
                 limits.context_window, limits.max_output_tokens,
                 limits.rpm, limits.rpd, limits.tpm, limits.tpd),
            )
        pg_conn.commit()
    except Exception as exc:
        logger.error("pg upsert_model_limits failed: %s", exc)
        try:
            pg_conn.rollback()
        except Exception:
            pass
        raise


def was_report_dispatched_pg(pg_conn: Any, report_key: str, bucket_start: str,
                              channel: str, target: str) -> bool:
    try:
        with pg_conn.cursor() as cur:
            cur.execute(
                """SELECT 1 FROM llm_report_dispatches
                   WHERE report_key=%s AND bucket_start=%s AND channel=%s AND target=%s
                   LIMIT 1""",
                (report_key, bucket_start, channel, target),
            )
            return cur.fetchone() is not None
    except Exception as exc:
        logger.error("pg was_report_dispatched failed: %s", exc)
        return False


def mark_report_dispatched_pg(pg_conn: Any, report_key: str, bucket_start: str,
                               channel: str, target: str) -> None:
    try:
        with pg_conn.cursor() as cur:
            cur.execute(
                """INSERT INTO llm_report_dispatches (report_key, bucket_start, channel, target)
                   VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                (report_key, bucket_start, channel, target),
            )
        pg_conn.commit()
    except Exception as exc:
        logger.error("pg mark_report_dispatched failed: %s", exc)
        try:
            pg_conn.rollback()
        except Exception:
            pass


def rate_limit_check_and_record_pg(
    pg_conn: Any,
    *,
    provider: str,
    model: str,
    bucket_minute: str,
    bucket_day: str,
    token_inc: int,
    rpm: "int | None",
    tpm: "int | None",
    rpd: "int | None",
    tpd: "int | None",
) -> "tuple[bool, str | None]":
    """Atomic check-and-increment using PostgreSQL row-level locking (no file lock)."""
    if rpm is None and tpm is None and rpd is None and tpd is None:
        return True, None
    if tpm is not None and token_inc > int(tpm):
        return False, f"request_exceeds_tpm: request={token_inc} tpm_limit={tpm}"

    try:
        with pg_conn.cursor() as cur:
            # Ensure rows exist, then lock them
            for kind, start in [("minute", bucket_minute), ("day", bucket_day)]:
                cur.execute(
                    """INSERT INTO llm_model_rate_buckets
                         (provider, model, bucket_kind, bucket_start, requests, tokens)
                       VALUES (%s,%s,%s,%s,0,0)
                       ON CONFLICT (provider, model, bucket_kind, bucket_start) DO NOTHING""",
                    (provider, model, kind, start),
                )

            # Lock rows for this provider/model atomically
            cur.execute(
                """SELECT bucket_kind, requests, tokens
                   FROM llm_model_rate_buckets
                   WHERE provider=%s AND model=%s
                     AND bucket_kind = ANY(%s)
                     AND bucket_start = ANY(%s)
                   FOR UPDATE""",
                (provider, model,
                 ["minute", "day"],
                 [bucket_minute, bucket_day]),
            )
            rows = {r[0]: (int(r[1] or 0), int(r[2] or 0)) for r in cur.fetchall()}
            min_reqs, min_toks = rows.get("minute", (0, 0))
            day_reqs, day_toks = rows.get("day", (0, 0))

            # Check limits
            if rpm is not None and min_reqs + 1 > int(rpm):
                pg_conn.rollback()
                return False, f"rpm_limit_exceeded: limit={rpm} used={min_reqs}"
            if tpm is not None and min_toks + token_inc > int(tpm):
                pg_conn.rollback()
                return False, f"tpm_limit_exceeded: limit={tpm} used={min_toks}"
            if rpd is not None and day_reqs + 1 > int(rpd):
                pg_conn.rollback()
                return False, f"rpd_limit_exceeded: limit={rpd} used={day_reqs}"
            if tpd is not None and day_toks + token_inc > int(tpd):
                pg_conn.rollback()
                return False, f"tpd_limit_exceeded: limit={tpd} used={day_toks}"

            # Increment
            for kind, start in [("minute", bucket_minute), ("day", bucket_day)]:
                cur.execute(
                    """UPDATE llm_model_rate_buckets
                       SET requests = requests + 1, tokens = tokens + %s, updated_at = NOW()
                       WHERE provider=%s AND model=%s AND bucket_kind=%s AND bucket_start=%s""",
                    (token_inc, provider, model, kind, start),
                )
        pg_conn.commit()
        return True, None
    except Exception as exc:
        logger.error("pg rate_limit_check failed: %s", exc)
        try:
            pg_conn.rollback()
        except Exception:
            pass
        raise


def rate_limit_add_tokens_pg(
    pg_conn: Any,
    *,
    provider: str,
    model: str,
    bucket_minute: str,
    bucket_day: str,
    tokens: int,
) -> None:
    if tokens <= 0:
        return
    try:
        with pg_conn.cursor() as cur:
            for kind, start in [("minute", bucket_minute), ("day", bucket_day)]:
                cur.execute(
                    """INSERT INTO llm_model_rate_buckets
                         (provider, model, bucket_kind, bucket_start, requests, tokens)
                       VALUES (%s,%s,%s,%s,0,%s)
                       ON CONFLICT (provider, model, bucket_kind, bucket_start)
                       DO UPDATE SET tokens = llm_model_rate_buckets.tokens + EXCLUDED.tokens,
                                     updated_at = NOW()""",
                    (provider, model, kind, start, tokens),
                )
        pg_conn.commit()
    except Exception as exc:
        logger.error("pg rate_limit_add_tokens failed: %s", exc)
        try:
            pg_conn.rollback()
        except Exception:
            pass


def _compute_token_quality(exact_total: int, estimated_total: int) -> str:
    if exact_total > 0 and estimated_total <= 0:
        return "exact"
    if exact_total <= 0 and estimated_total > 0:
        return "estimated"
    if exact_total <= 0 and estimated_total <= 0:
        return "n/a"
    return "mixed"


def summarize_usage(
    conn: sqlite3.Connection,
    start_at: datetime,
    end_at: datetime,
) -> list[UsageSummaryRow]:
    window_minutes = max((end_at - start_at).total_seconds() / 60.0, 1.0)
    rows = conn.execute(
        """
        SELECT
          service,
          provider,
          model,
          request_kind,
          COUNT(*) AS attempts,
          SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) AS successes,
          SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) AS failures,
          SUM(CASE WHEN token_accuracy = 'exact' THEN COALESCE(input_tokens, 0) ELSE 0 END) AS input_tokens_exact,
          SUM(CASE WHEN token_accuracy = 'exact' THEN COALESCE(output_tokens, 0) ELSE 0 END) AS output_tokens_exact,
          SUM(CASE WHEN token_accuracy = 'exact' THEN COALESCE(total_tokens, 0) ELSE 0 END) AS total_tokens_exact,
          SUM(CASE WHEN token_accuracy = 'estimated' THEN COALESCE(input_tokens, 0) ELSE 0 END) AS input_tokens_estimated,
          SUM(CASE WHEN token_accuracy = 'estimated' THEN COALESCE(output_tokens, 0) ELSE 0 END) AS output_tokens_estimated,
          SUM(CASE WHEN token_accuracy = 'estimated' THEN COALESCE(total_tokens, 0) ELSE 0 END) AS total_tokens_estimated
        FROM usage_events
        WHERE timestamp >= ? AND timestamp < ?
        GROUP BY service, provider, model, request_kind
        ORDER BY attempts DESC, service, provider, model
        """,
        (start_at.isoformat(), end_at.isoformat()),
    ).fetchall()

    minute_rows = conn.execute(
        """
        SELECT
          service,
          provider,
          model,
          request_kind,
          substr(timestamp, 1, 16) AS minute_bucket,
          COUNT(*) AS minute_attempts
        FROM usage_events
        WHERE timestamp >= ? AND timestamp < ?
        GROUP BY service, provider, model, request_kind, minute_bucket
        """,
        (start_at.isoformat(), end_at.isoformat()),
    ).fetchall()
    minute_map: dict[tuple[str, str, str, str], int] = {}
    for row in minute_rows:
        key = (row["service"], row["provider"], row["model"], row["request_kind"])
        minute_map[key] = max(minute_map.get(key, 0), int(row["minute_attempts"]))

    output: list[UsageSummaryRow] = []
    for row in rows:
        key = (row["service"], row["provider"], row["model"], row["request_kind"])
        attempts = int(row["attempts"])
        exact_total = int(row["total_tokens_exact"] or 0)
        estimated_total = int(row["total_tokens_estimated"] or 0)
        output.append(
            UsageSummaryRow(
                service=row["service"],
                provider=row["provider"],
                model=row["model"],
                request_kind=row["request_kind"],
                attempts=attempts,
                successes=int(row["successes"] or 0),
                failures=int(row["failures"] or 0),
                rpm_avg=attempts / window_minutes,
                rpm_peak=minute_map.get(key, 0),
                input_tokens_exact=int(row["input_tokens_exact"] or 0),
                output_tokens_exact=int(row["output_tokens_exact"] or 0),
                total_tokens_exact=exact_total,
                input_tokens_estimated=int(row["input_tokens_estimated"] or 0),
                output_tokens_estimated=int(row["output_tokens_estimated"] or 0),
                total_tokens_estimated=estimated_total,
                token_quality=_compute_token_quality(exact_total, estimated_total),
            )
        )
    return output


def was_report_dispatched(
    conn: sqlite3.Connection,
    report_key: str,
    bucket_start: datetime,
    channel: str,
    target: str,
) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM report_dispatches
        WHERE report_key = ? AND bucket_start = ? AND channel = ? AND target = ?
        LIMIT 1
        """,
        (report_key, bucket_start.isoformat(), channel, target),
    ).fetchone()
    return row is not None


def mark_report_dispatched(
    conn: sqlite3.Connection,
    report_key: str,
    bucket_start: datetime,
    channel: str,
    target: str,
) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO report_dispatches (report_key, bucket_start, channel, target)
        VALUES (?, ?, ?, ?)
        """,
        (report_key, bucket_start.isoformat(), channel, target),
    )
    conn.commit()
