"""
Tool: service
Função: Faz passthrough HTTP para upstreams de modelo e registra eventos brutos no storage.
Usar quando: O proxy receber chamadas OpenAI-compatible ou Ollama-compatible.

ENV_VARS:
  - (nenhuma; settings injetadas externamente)

DB_TABLES:
  - usage_events: leitura+escrita
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import re
import uuid
from typing import Any, AsyncIterator
from urllib.parse import unquote
from zoneinfo import ZoneInfo

import httpx

from llm_usage_telemetry.settings import TelemetrySettings
from llm_usage_telemetry.openclaw_sync import sync_model_limits_from_openclaw_config_path
from llm_usage_telemetry.model_limits_catalog import DEFAULT_MODEL_LIMITS_CATALOG_PATH
from llm_usage_telemetry.storage import (
    UsageEvent,
    connect_db,
    connect_pg,
    ensure_pg_conn,
    get_model_limits,
    get_model_limits_pg,
    initialize_pg_schema_full,
    initialize_schema,
    mark_report_dispatched_pg,
    rate_limit_add_tokens_pg,
    rate_limit_check_and_record_pg,
    record_usage_event,
    record_usage_event_pg,
    upsert_model_limits,
    upsert_model_limits_pg,
    was_report_dispatched_pg,
)
from llm_usage_telemetry.upstreams import parse_target_model, resolve_upstream


@dataclass(slots=True)
class ProxyResult:
    status_code: int
    body: Any


@dataclass(slots=True)
class ProxyStreamResult:
    status_code: int
    iterator: AsyncIterator[bytes]
    headers: dict[str, str] | None = None
    media_type: str = "text/event-stream"


_TELEMETRY_MARKER_RE = re.compile(r"^\[telemetry (?P<body>[^\]]+)\]\s*", re.IGNORECASE)
_SKILL_PATTERNS = (
    re.compile(r"\bexecute a skill\s+([a-z0-9][a-z0-9_-]*)", re.IGNORECASE),
    re.compile(r"\busing skill:\s*([a-z0-9][a-z0-9_-]*)", re.IGNORECASE),
    re.compile(r"\buse(?:\s+the)?\s+skill\s+([a-z0-9][a-z0-9_-]*)", re.IGNORECASE),
)
_DEFAULT_RPM_BY_PROVIDER: dict[str, int] = {
    "groq": 30,
    "mistral": 20,
    "ollama": 60,
}
_DEFAULT_RPM_FALLBACK = 10


def _extract_header(headers: dict[str, str], name: str) -> str:
    return headers.get(name) or headers.get(name.lower()) or ""


def _rough_token_estimate(text: str) -> int:
    normalized = (text or "").strip()
    if not normalized:
        return 0
    return max(1, (len(normalized) + 3) // 4)


def _word_count(text: str) -> int:
    normalized = (text or "").strip()
    if not normalized:
        return 0
    return len(normalized.split())


def _safe_json_dumps(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        return str(value)


def _estimate_embedding_input_tokens(payload: dict[str, Any]) -> int:
    raw_input = payload.get("input", payload.get("prompt", ""))
    if isinstance(raw_input, str):
        return _rough_token_estimate(raw_input)
    if isinstance(raw_input, list):
        joined = " ".join(str(item) for item in raw_input)
        return _rough_token_estimate(joined)
    return _rough_token_estimate(str(raw_input))


def _estimate_chat_input_tokens(payload: dict[str, Any]) -> int:
    messages = payload.get("messages")
    if isinstance(messages, list):
        parts: list[str] = []
        for message in messages:
            if not isinstance(message, dict):
                parts.append(str(message))
                continue
            role = str(message.get("role", "user"))
            content = _stringify_content(message.get("content"))
            if content:
                parts.append(f"{role}: {content}")
        return _rough_token_estimate("\n".join(parts))

    raw_input = payload.get("input", payload.get("prompt", ""))
    return _rough_token_estimate(_stringify_content(raw_input))


def _estimate_chat_output_tokens(response_json: Any) -> int:
    if not isinstance(response_json, dict):
        return 0

    output_chunks: list[str] = []

    output_text = response_json.get("output_text")
    if output_text:
        output_chunks.append(str(output_text))

    choices = response_json.get("choices")
    if isinstance(choices, list):
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            message = choice.get("message") or {}
            if isinstance(message, dict):
                content = _stringify_content(message.get("content"))
                if content:
                    output_chunks.append(content)
            delta = choice.get("delta") or {}
            if isinstance(delta, dict):
                content = _stringify_content(delta.get("content"))
                if content:
                    output_chunks.append(content)

    output_items = response_json.get("output")
    if isinstance(output_items, list):
        for item in output_items:
            if not isinstance(item, dict):
                output_chunks.append(str(item))
                continue
            content = item.get("content")
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict):
                        text = part.get("text") or part.get("content")
                        if text:
                            output_chunks.append(str(text))
            else:
                text = item.get("text") or item.get("content")
                if text:
                    output_chunks.append(_stringify_content(text))

    return _rough_token_estimate("\n".join(chunk for chunk in output_chunks if chunk))


def _extract_request_text(payload: dict[str, Any]) -> str:
    messages = payload.get("messages")
    if isinstance(messages, list):
        parts: list[str] = []
        for message in messages:
            if not isinstance(message, dict):
                parts.append(str(message))
                continue
            role = str(message.get("role", "user"))
            content = _stringify_content(message.get("content"))
            if content:
                parts.append(f"{role}: {content}")
        return "\n".join(parts)

    raw_input = payload.get("input", payload.get("prompt", ""))
    return _stringify_content(raw_input)


def _extract_response_text(response_json: Any) -> str:
    if not isinstance(response_json, dict):
        return str(response_json)

    chunks: list[str] = []
    output_text = response_json.get("output_text")
    if output_text:
        chunks.append(str(output_text))

    choices = response_json.get("choices")
    if isinstance(choices, list):
        for choice in choices:
            if not isinstance(choice, dict):
                chunks.append(str(choice))
                continue
            message = choice.get("message") or {}
            if isinstance(message, dict):
                content = _stringify_content(message.get("content"))
                if content:
                    chunks.append(content)
            delta = choice.get("delta") or {}
            if isinstance(delta, dict):
                content = _stringify_content(delta.get("content"))
                if content:
                    chunks.append(content)

    outputs = response_json.get("outputs")
    if isinstance(outputs, list):
        for item in outputs:
            if not isinstance(item, dict):
                chunks.append(str(item))
                continue
            text = item.get("text")
            if text:
                chunks.append(str(text))
            content = item.get("content")
            if content:
                chunks.append(_stringify_content(content))

    output_items = response_json.get("output")
    if isinstance(output_items, list):
        for item in output_items:
            if not isinstance(item, dict):
                chunks.append(str(item))
                continue
            text = item.get("text")
            if text:
                chunks.append(str(text))
            content = item.get("content")
            if content:
                chunks.append(_stringify_content(content))

    error = response_json.get("error")
    if isinstance(error, dict):
        message = error.get("message")
        if message:
            chunks.append(str(message))

    return "\n".join(chunk for chunk in chunks if chunk)


def _build_payload_capture(mode: str, value: Any) -> str | None:
    normalized_mode = (mode or "off").lower()
    if normalized_mode == "off":
        return None
    serialized = _safe_json_dumps(value)
    if normalized_mode == "preview":
        return serialized[:4000]
    return serialized


_VERSIONED_BASE_RE = re.compile(r"/v\d+$")


def _join_upstream_url(base_url: str, request_path: str) -> str:
    normalized_base = base_url.rstrip("/")
    if request_path.startswith("/v1/") and normalized_base.endswith("/v1"):
        return normalized_base + request_path[len("/v1") :]
    if request_path.startswith("/v1/") and (
        normalized_base.endswith("/openai") or normalized_base.endswith("/openapi")
    ):
        return normalized_base + request_path[len("/v1") :]
    if request_path.startswith("/api/") and normalized_base.endswith("/v1"):
        return normalized_base[: -len("/v1")] + request_path
    # Providers whose base URL ends with /v{N} (e.g. /v4 for z.ai) use their own
    # version segment in place of the standard /v1 prefix.
    if request_path.startswith("/v1/") and _VERSIONED_BASE_RE.search(normalized_base):
        return normalized_base + request_path[len("/v1") :]
    return normalized_base + request_path


def _normalize_upstream_payload(provider: str, payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)

    if provider == "google":
        # Gemini's native endpoints reject some OpenAI-only fields that other providers tolerate.
        for field_name in ("store", "seed", "parallel_tool_calls", "stream_options"):
            normalized.pop(field_name, None)
    elif provider != "openai":
        # `store` is a Responses-only knob; many OpenAI-compatible upstreams reject it.
        normalized.pop("store", None)

    return normalized


def _parse_telemetry_kv_blob(blob: str) -> dict[str, str]:
    output: dict[str, str] = {}
    for part in (blob or "").split():
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        key = key.strip()
        if not key:
            continue
        output[key] = unquote(value.strip())
    return output


def _strip_telemetry_marker_from_text(text: str) -> tuple[str, dict[str, str]]:
    if not isinstance(text, str):
        return text, {}
    match = _TELEMETRY_MARKER_RE.match(text)
    if not match:
        return text, {}
    metadata = _parse_telemetry_kv_blob(match.group("body"))
    return text[match.end() :].lstrip(), metadata


def _sanitize_payload_provenance(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str], str]:
    sanitized = dict(payload)
    inferred_prompt_fragments: list[str] = []

    messages = payload.get("messages")
    if isinstance(messages, list):
        new_messages = []
        marker_meta: dict[str, str] = {}
        for index, message in enumerate(messages):
            if not isinstance(message, dict):
                new_messages.append(message)
                continue
            new_message = dict(message)
            content = new_message.get("content")
            if index == 0 and isinstance(content, str):
                stripped, current_meta = _strip_telemetry_marker_from_text(content)
                if current_meta and not marker_meta:
                    marker_meta = current_meta
                new_message["content"] = stripped
                if stripped:
                    inferred_prompt_fragments.append(stripped)
            elif isinstance(content, str) and content:
                inferred_prompt_fragments.append(content)
            new_messages.append(new_message)
        sanitized["messages"] = new_messages
        return sanitized, marker_meta, "\n".join(inferred_prompt_fragments)

    input_value = payload.get("input", payload.get("prompt"))
    if isinstance(input_value, str):
        stripped, marker_meta = _strip_telemetry_marker_from_text(input_value)
        if "input" in sanitized:
            sanitized["input"] = stripped
        elif "prompt" in sanitized:
            sanitized["prompt"] = stripped
        return sanitized, marker_meta, stripped

    return sanitized, {}, ""


def _infer_skill_name(prompt_text: str) -> str | None:
    for pattern in _SKILL_PATTERNS:
        match = pattern.search(prompt_text or "")
        if match:
            return match.group(1)
    return None


def _stringify_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                chunks.append(str(item.get("text", "")))
            else:
                chunks.append(str(item))
        return "\n".join(chunk for chunk in chunks if chunk)
    if content is None:
        return ""
    return str(content)


def _build_google_interactions_input(payload: dict[str, Any]) -> list[dict[str, str]]:
    messages = payload.get("messages")
    system_chunks: list[str] = []
    turns: list[dict[str, str]] = []

    if isinstance(messages, list) and messages:
        for message in messages:
            role = str(message.get("role", "user"))
            content = _stringify_content(message.get("content"))
            if not content:
                continue
            if role == "system":
                system_chunks.append(content)
                continue
            mapped_role = "model" if role == "assistant" else "user"
            turns.append({"role": mapped_role, "content": content})
    else:
        raw_input = payload.get("input", payload.get("prompt", ""))
        content = _stringify_content(raw_input)
        if content:
            turns.append({"role": "user", "content": content})

    if system_chunks:
        system_prefix = "\n\n".join(system_chunks).strip()
        if turns and turns[0]["role"] == "user":
            turns[0]["content"] = f"{system_prefix}\n\n{turns[0]['content']}".strip()
        else:
            turns.insert(0, {"role": "user", "content": system_prefix})

    return turns


def _build_google_native_request(
    request_kind: str,
    base_url: str,
    model: str,
    payload: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    normalized_base = base_url.rstrip("/")
    if request_kind == "embedding":
        raw_input = payload.get("input", payload.get("prompt", ""))
        return (
            f"{normalized_base}/models/{model}:embedContent",
            {
                "model": f"models/{model}",
                "content": {"parts": [{"text": _stringify_content(raw_input)}]},
            },
        )

    body: dict[str, Any] = {
        "model": model,
        "input": _build_google_interactions_input(payload),
    }
    return f"{normalized_base}/interactions", body


def _extract_error_details(status_code: int, response_json: Any, response_text: str) -> tuple[str, str]:
    """
    Return (error_code, error_message) from assorted OpenAI-compatible and provider-native shapes.

    Notably, some upstreams (e.g. Gemini) return errors wrapped in a list, and we don't want
    to crash while recording telemetry.
    """

    fallback_code = f"http_{status_code}"
    fallback_message = (response_text or str(response_json))[:2000]

    if isinstance(response_json, list) and response_json:
        first = response_json[0]
        if isinstance(first, dict):
            inner = first.get("error")
            if isinstance(inner, dict):
                code = inner.get("code") or fallback_code
                message = inner.get("message") or fallback_message
                return str(code), str(message)
        return fallback_code, str(first)[:2000]

    if not isinstance(response_json, dict):
        return fallback_code, fallback_message

    error_value = response_json.get("error")
    if isinstance(error_value, dict):
        code = error_value.get("code") or fallback_code
        message = error_value.get("message") or fallback_message
        return str(code), str(message)

    if isinstance(error_value, list) and error_value:
        first = error_value[0]
        if isinstance(first, dict):
            inner = first.get("error")
            if isinstance(inner, dict):
                code = inner.get("code") or fallback_code
                message = inner.get("message") or fallback_message
                return str(code), str(message)
        return fallback_code, str(first)[:2000]

    return fallback_code, fallback_message


_MAX_COMPLETION_LIMIT_RE = re.compile(
    r"max_completion_tokens`\s+must\s+be\s+less\s+than\s+or\s+equal\s+to\s+`(?P<limit>\d+)`",
    re.IGNORECASE,
)
_TPM_LIMIT_RE = re.compile(r"tokens per minute \(TPM\):\s*Limit\s+(?P<limit>\d+)", re.IGNORECASE)


def _fetch_google_model_metadata(
    *,
    base_url: str,
    api_key: str,
    auth_mode: str,
    timeout_seconds: float = 20.0,
) -> tuple[dict[str, tuple[int | None, int | None]], dict[str, Any] | None]:
    if not api_key:
        return {}, {"error": "google_api_key_missing"}

    base = (base_url or "").rstrip("/")
    if not base:
        return {}, {"error": "google_base_url_missing"}
    if "generativelanguage.googleapis.com" not in base:
        return {}, {"error": "google_metadata_unsupported_base_url", "base_url": base}

    url = f"{base}/models"
    headers: dict[str, str] = {}
    if auth_mode == "x-goog-api-key":
        headers["x-goog-api-key"] = api_key
    else:
        headers["authorization"] = f"Bearer {api_key}"

    try:
        response = httpx.get(
            url,
            headers=headers,
            params={"pageSize": "1000"},
            timeout=timeout_seconds,
        )
    except Exception as exc:  # pragma: no cover - network failure is non-deterministic
        return {}, {"error": "google_metadata_request_failed", "message": str(exc)}

    if response.status_code >= 400:
        return {}, {
            "error": "google_metadata_http_error",
            "status_code": response.status_code,
            "body": response.text[:500],
        }

    try:
        payload = response.json()
    except Exception as exc:
        return {}, {"error": "google_metadata_invalid_json", "message": str(exc)}

    items = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return {}, {"error": "google_metadata_unexpected_response"}

    out: dict[str, tuple[int | None, int | None]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "")
        if not name:
            continue
        model_id = name.split("/", 1)[1] if name.startswith("models/") and "/" in name else name

        try:
            input_limit = item.get("inputTokenLimit")
            output_limit = item.get("outputTokenLimit")
            input_tokens = int(input_limit) if input_limit is not None else None
            output_tokens = int(output_limit) if output_limit is not None else None
        except Exception:
            input_tokens = None
            output_tokens = None

        out[model_id] = (input_tokens, output_tokens)

    return out, None


def _enrich_google_model_limits(conn: Any, *, settings: TelemetrySettings) -> dict[str, Any] | None:
    if conn is None:
        return None

    rows = conn.execute(
        """
        SELECT model, context_window, max_output_tokens, enabled
        FROM model_limits
        WHERE provider = 'google'
        ORDER BY model
        """
    ).fetchall()
    if not rows:
        return {"ok": True, "updated": 0, "skipped": 0, "note": "no google models in model_limits"}

    pending: list[dict[str, Any]] = []
    for row in rows:
        if int(row["enabled"] or 0) != 1:
            continue
        if row["context_window"] is None or row["max_output_tokens"] is None:
            pending.append(
                {
                    "model": row["model"],
                    "context_window": row["context_window"],
                    "max_output_tokens": row["max_output_tokens"],
                }
            )
    if not pending:
        return {"ok": True, "updated": 0, "skipped": 0}

    # Resolve upstream config using one of the pending models (auth/base_url are shared at provider level).
    probe_model = pending[0]["model"]
    try:
        probe_target = parse_target_model(f"usage-router/google/{probe_model}")
        upstream = resolve_upstream(probe_target)
    except Exception as exc:
        return {"ok": False, "error": "google_metadata_upstream_unavailable", "message": str(exc)}

    metadata, error = _fetch_google_model_metadata(
        base_url=upstream.base_url,
        api_key=upstream.api_key,
        auth_mode=upstream.auth_mode,
        timeout_seconds=float(getattr(settings, "proxy_timeout_seconds", 20.0)),
    )
    if error:
        return {"ok": False, **error}

    updated = 0
    skipped = 0
    missing = 0
    for item in pending:
        model = str(item["model"])
        limits = metadata.get(model)
        if limits is None:
            missing += 1
            continue
        context_window, max_output_tokens = limits
        context_to_set = None
        if item.get("context_window") is None and context_window is not None and context_window > 0:
            context_to_set = int(context_window)
        max_out_to_set = None
        if item.get("max_output_tokens") is None and max_output_tokens is not None and max_output_tokens > 0:
            max_out_to_set = int(max_output_tokens)
        if context_to_set is None and max_out_to_set is None:
            skipped += 1
            continue
        upsert_model_limits(
            conn,
            "google",
            model,
            context_window=context_to_set,
            max_output_tokens=max_out_to_set,
        )
        updated += 1

    return {
        "ok": True,
        "updated": updated,
        "skipped": skipped,
        "missing": missing,
        "catalog_size": len(metadata),
        "base_url": upstream.base_url,
    }


def _maybe_learn_model_limits(
    conn: Any,
    *,
    provider: str,
    model: str,
    http_status: int | None,
    error_code: str | None,
    error_message: str | None,
) -> None:
    if not conn or not provider or not model or not error_message:
        return
    status = int(http_status or 0)
    message = str(error_message)

    if status == 400:
        match = _MAX_COMPLETION_LIMIT_RE.search(message)
        if match:
            try:
                limit = int(match.group("limit"))
            except Exception:
                limit = None
            if limit and limit > 0:
                upsert_model_limits(conn, provider, model, max_output_tokens=limit)

    if status in {413, 429}:
        match = _TPM_LIMIT_RE.search(message)
        if match:
            try:
                limit = int(match.group("limit"))
            except Exception:
                limit = None
            if limit and limit > 0:
                upsert_model_limits(conn, provider, model, tpm=limit)

    if error_code in {"model_not_found"} or status == 404:
        upsert_model_limits(conn, provider, model, enabled=False, disabled_reason="model_not_found")
    if error_code in {"model_terms_required"}:
        upsert_model_limits(conn, provider, model, enabled=False, disabled_reason="model_terms_required")


def _bucket_start_minute(now: datetime) -> datetime:
    return now.replace(second=0, microsecond=0)


def _bucket_start_day(now: datetime, tz_name: str) -> datetime:
    tz = ZoneInfo(tz_name or "UTC")
    localized = now.astimezone(tz)
    day_start_local = localized.replace(hour=0, minute=0, second=0, microsecond=0)
    return day_start_local.astimezone(timezone.utc)


def _rate_limit_check_and_record(
    conn: Any,
    *,
    pg_conn: Any = None,
    provider: str,
    model: str,
    tz_name: str,
    limits: Any,
    tokens: int,
) -> tuple[bool, str | None]:
    if (not conn and pg_conn is None) or not limits:
        return True, None

    rpm = getattr(limits, "rpm", None)
    tpm = getattr(limits, "tpm", None)
    rpd = getattr(limits, "rpd", None)
    tpd = getattr(limits, "tpd", None)
    if rpm is None and tpm is None and rpd is None and tpd is None:
        return True, None

    now = datetime.now(timezone.utc)
    minute_start = _bucket_start_minute(now).isoformat()
    day_start = _bucket_start_day(now, tz_name).isoformat()
    token_inc = max(int(tokens or 0), 0)

    # Hard reject: single request larger than the model's entire minute TPM budget.
    if tpm is not None and token_inc > int(tpm):
        return False, f"request_exceeds_tpm: request={token_inc} tpm_limit={tpm}"

    # Use PostgreSQL (row-level locking) when available — avoids SQLite file lock
    if pg_conn is not None:
        return rate_limit_check_and_record_pg(
            pg_conn,
            provider=provider, model=model,
            bucket_minute=minute_start, bucket_day=day_start,
            token_inc=token_inc, rpm=rpm, tpm=tpm, rpd=rpd, tpd=tpd,
        )

    def current(kind: str, start: str) -> tuple[int, int]:
        row = conn.execute(
            """
            SELECT requests, tokens
            FROM model_rate_buckets
            WHERE provider = ? AND model = ? AND bucket_kind = ? AND bucket_start = ?
            """,
            (provider, model, kind, start),
        ).fetchone()
        if not row:
            return 0, 0
        return int(row["requests"] or 0), int(row["tokens"] or 0)

    def bump(kind: str, start: str, req_inc: int, tok_inc: int) -> None:
        conn.execute(
            """
            INSERT INTO model_rate_buckets (provider, model, bucket_kind, bucket_start, requests, tokens)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(provider, model, bucket_kind, bucket_start)
            DO UPDATE SET
              requests = requests + excluded.requests,
              tokens = tokens + excluded.tokens,
              updated_at = CURRENT_TIMESTAMP
            """,
            (provider, model, kind, start, req_inc, tok_inc),
        )

    conn.execute("BEGIN IMMEDIATE")
    try:
        if rpm is not None or tpm is not None:
            reqs, toks = current("minute", minute_start)
            next_reqs = reqs + 1
            next_toks = toks + token_inc
            if rpm is not None and next_reqs > int(rpm):
                conn.rollback()
                return False, f"rpm_limit_exceeded: limit={rpm} used={reqs}"
            if tpm is not None and next_toks > int(tpm):
                conn.rollback()
                return False, f"tpm_limit_exceeded: limit={tpm} used={toks}"

        if rpd is not None or tpd is not None:
            reqs, toks = current("day", day_start)
            next_reqs = reqs + 1
            next_toks = toks + token_inc
            if rpd is not None and next_reqs > int(rpd):
                conn.rollback()
                return False, f"rpd_limit_exceeded: limit={rpd} used={reqs}"
            if tpd is not None and next_toks > int(tpd):
                conn.rollback()
                return False, f"tpd_limit_exceeded: limit={tpd} used={toks}"

        if rpm is not None or tpm is not None:
            bump("minute", minute_start, 1, token_inc)
        if rpd is not None or tpd is not None:
            bump("day", day_start, 1, token_inc)
        conn.commit()
        return True, None
    except Exception:
        conn.rollback()
        raise


def _rate_limit_add_tokens(
    conn: Any,
    *,
    pg_conn: Any = None,
    provider: str,
    model: str,
    tz_name: str,
    limits: Any,
    tokens: int,
) -> None:
    if (not conn and pg_conn is None) or not limits:
        return

    tpm = getattr(limits, "tpm", None)
    tpd = getattr(limits, "tpd", None)
    if tpm is None and tpd is None:
        return

    token_inc = int(tokens or 0)
    if token_inc <= 0:
        return

    now = datetime.now(timezone.utc)
    minute_start = _bucket_start_minute(now).isoformat()
    day_start = _bucket_start_day(now, tz_name).isoformat()

    if pg_conn is not None:
        rate_limit_add_tokens_pg(
            pg_conn, provider=provider, model=model,
            bucket_minute=minute_start, bucket_day=day_start, tokens=token_inc,
        )
        return

    def bump(kind: str, start: str, tok_inc: int) -> None:
        conn.execute(
            """
            INSERT INTO model_rate_buckets (provider, model, bucket_kind, bucket_start, requests, tokens)
            VALUES (?, ?, ?, ?, 0, ?)
            ON CONFLICT(provider, model, bucket_kind, bucket_start)
            DO UPDATE SET
              tokens = tokens + excluded.tokens,
              updated_at = CURRENT_TIMESTAMP
            """,
            (provider, model, kind, start, tok_inc),
        )

    conn.execute("BEGIN IMMEDIATE")
    try:
        if tpm is not None:
            bump("minute", minute_start, token_inc)
        if tpd is not None:
            bump("day", day_start, token_inc)
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def _translate_google_native_response(
    request_kind: str,
    model: str,
    response_json: dict[str, Any],
) -> dict[str, Any]:
    usage_metadata = response_json.get("usage_metadata") or response_json.get("usageMetadata") or {}
    prompt_tokens = usage_metadata.get("input_tokens") or usage_metadata.get("promptTokenCount")
    completion_tokens = usage_metadata.get("output_tokens") or usage_metadata.get("candidatesTokenCount")
    total_tokens = usage_metadata.get("total_tokens") or usage_metadata.get("totalTokenCount")

    if request_kind == "embedding":
        embedding = ((response_json.get("embedding") or {}).get("values")) or []
        return {
            "object": "list",
            "model": model,
            "data": [{"object": "embedding", "index": 0, "embedding": embedding}],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            },
        }

    outputs = response_json.get("outputs") or []
    output_text = ""
    for item in outputs:
        if isinstance(item, dict) and item.get("type") == "text":
            output_text = str(item.get("text", ""))
            break
    if not output_text and outputs:
        first = outputs[-1]
        if isinstance(first, dict):
            output_text = str(first.get("text", "") or first.get("content", ""))
        else:
            output_text = str(first)
    return {
        "id": response_json.get("id") or response_json.get("responseId"),
        "object": "chat.completion",
        "model": model,
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": output_text,
                },
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        },
    }


class MetricsProxyService:
    def __init__(self, settings: TelemetrySettings):
        self.settings = settings
        self.conn = connect_db(settings.db_path)
        initialize_schema(self.conn)
        self._pg_url = getattr(settings, "pg_url", "")
        self.pg_conn = None
        if self._pg_url:
            self.pg_conn = connect_pg(self._pg_url)
            if self.pg_conn is not None:
                initialize_pg_schema_full(self.pg_conn)
                print("[llm-metrics-proxy] ALL tables → PostgreSQL (rate_buckets, model_limits, dispatches, usage_events)")
        self.last_openclaw_sync: dict[str, Any] | None = None
        if getattr(settings, "sync_openclaw_models", False):
            try:
                self.last_openclaw_sync = self.sync_openclaw_models()
            except Exception as exc:  # pragma: no cover - startup should be resilient
                print(f"[llm-metrics-proxy] openclaw sync failed: {exc}")

    def sync_openclaw_models(self) -> dict[str, Any]:
        result = sync_model_limits_from_openclaw_config_path(
            self.conn,
            getattr(self.settings, "openclaw_config_path", "/openclaw/openclaw.json"),
            default_rpm_by_provider=_DEFAULT_RPM_BY_PROVIDER,
            rpm_fallback=_DEFAULT_RPM_FALLBACK,
            strict=bool(getattr(self.settings, "sync_openclaw_models_strict", False)),
            catalog_path=getattr(
                self.settings,
                "model_limits_catalog_path",
                DEFAULT_MODEL_LIMITS_CATALOG_PATH,
            ),
        )
        if isinstance(result, dict) and result.get("ok"):
            google = _enrich_google_model_limits(self.conn, settings=self.settings)
            if google is not None:
                result["google_enrich"] = google
        return result

    def _record(self, event: UsageEvent) -> None:
        if self.pg_conn is not None:
            try:
                record_usage_event_pg(self.pg_conn, event)
                return
            except Exception as exc:
                logger.warning("pg write failed (%s), reconnecting…", exc)
                try:
                    self.pg_conn = connect_pg(self._pg_url)
                    if self.pg_conn is not None:
                        record_usage_event_pg(self.pg_conn, event)
                        return
                except Exception as exc2:
                    logger.error("pg reconnect failed (%s), falling back to SQLite", exc2)
                    self.pg_conn = None
        record_usage_event(self.conn, event)

    def close(self) -> None:
        self.conn.close()
        if self.pg_conn is not None:
            self.pg_conn.close()

    async def handle_openai_request(
        self,
        request_kind: str,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> ProxyResult | ProxyStreamResult:
        return await self._forward_request(
            request_path={
                "chat": "/v1/chat/completions",
                "responses": "/v1/responses",
                "embedding": "/v1/embeddings",
            }[request_kind],
            request_kind=request_kind,
            payload=payload,
            headers=headers,
        )

    async def handle_ollama_embedding(
        self,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> ProxyResult | ProxyStreamResult:
        return await self._forward_request(
            request_path="/api/embeddings",
            request_kind="embedding",
            payload=payload,
            headers=headers,
        )

    async def _forward_request(
        self,
        request_path: str,
        request_kind: str,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> ProxyResult | ProxyStreamResult:
        started_at = datetime.now(timezone.utc)
        service = _extract_header(headers, "x-usage-service") or "unknown"
        logical_request_id = _extract_header(headers, "x-logical-request-id") or str(uuid.uuid4())
        origin_type = _extract_header(headers, "x-usage-origin-type") or None
        origin_name = _extract_header(headers, "x-usage-origin-name") or None
        trigger_type = _extract_header(headers, "x-usage-trigger-type") or None
        trigger_name = _extract_header(headers, "x-usage-trigger-name") or None
        agent_name = _extract_header(headers, "x-usage-agent-name") or None

        sanitized_payload, prompt_meta, prompt_text = _sanitize_payload_provenance(payload)
        if not trigger_type:
            trigger_type = prompt_meta.get("trigger_type") or None
        if not trigger_name:
            trigger_name = prompt_meta.get("trigger_name") or None
        if not agent_name:
            agent_name = prompt_meta.get("agent_name") or None
        inferred_skill = _infer_skill_name(prompt_text)
        if inferred_skill and (
            not origin_type
            or not origin_name
            or (origin_type == "service" and origin_name == service)
        ):
            origin_type = "skill"
            origin_name = inferred_skill

        model_ref = sanitized_payload.get("model") or ""
        if model_ref.startswith("usage-router/"):
            target = parse_target_model(model_ref)
        elif isinstance(model_ref, str) and "/" in model_ref:
            target = parse_target_model(f"usage-router/{model_ref}")
        else:
            provider = _extract_header(headers, "x-target-provider")
            model = _extract_header(headers, "x-target-model") or model_ref
            if not provider or not model:
                raise ValueError("missing target provider/model")
            target = parse_target_model(f"usage-router/{provider}/{model}")

        # Reconecta PG se a conexão estiver fechada (evita 500 por pool esgotado)
        if self._pg_url:
            self.pg_conn = ensure_pg_conn(self.pg_conn, self._pg_url)

        upstream = resolve_upstream(target)
        model_limits = (get_model_limits_pg(self.pg_conn, target.provider, target.model)
                        if self.pg_conn else
                        get_model_limits(self.conn, target.provider, target.model))
        if model_limits is None:
            from llm_usage_telemetry.storage import ModelLimits as _ML
            default_rpm = _DEFAULT_RPM_BY_PROVIDER.get(target.provider, _DEFAULT_RPM_FALLBACK)
            upsert_model_limits(self.conn, target.provider, target.model, rpm=default_rpm)
            if self.pg_conn:
                upsert_model_limits_pg(self.pg_conn, _ML(
                    provider=target.provider, model=target.model, enabled=True,
                    disabled_reason=None, context_window=None, max_output_tokens=None,
                    rpm=default_rpm, rpd=None, tpm=None, tpd=None,
                ))
            model_limits = (get_model_limits_pg(self.pg_conn, target.provider, target.model)
                            if self.pg_conn else
                            get_model_limits(self.conn, target.provider, target.model))
        if model_limits and not model_limits.enabled:
            return ProxyResult(
                status_code=400,
                body={
                    "error": {
                        "code": "model_disabled",
                        "message": model_limits.disabled_reason or "model disabled by policy",
                    }
                },
            )
        upstream_payload = _normalize_upstream_payload(upstream.provider, sanitized_payload)
        upstream_payload["model"] = upstream.upstream_model
        request_headers = {"Content-Type": "application/json"}

        if upstream.api_key and upstream.auth_mode == "bearer":
            request_headers["Authorization"] = f"Bearer {upstream.api_key}"
        elif upstream.api_key and upstream.auth_mode == "x-goog-api-key":
            request_headers["x-goog-api-key"] = upstream.api_key

        status_code = 500
        response_json: Any = {}
        error_code = None
        error_message = None
        token_accuracy = "unavailable"
        input_tokens = None
        output_tokens = None
        total_tokens = None
        response_id = None
        request_text = _extract_request_text(sanitized_payload)
        request_payload_capture = _build_payload_capture(self.settings.capture_payloads, sanitized_payload)
        response_text = ""
        response_payload_capture = None
        stream_requested = bool(sanitized_payload.get("stream")) and request_kind in {"chat", "responses"}
        telemetry_deferred = False

        try:
            if request_kind in {"chat", "responses"} and model_limits and model_limits.max_output_tokens:
                max_out = max(1, int(model_limits.max_output_tokens))
                if "max_tokens" in upstream_payload:
                    token_key = "max_tokens"
                elif "max_completion_tokens" in upstream_payload:
                    token_key = "max_completion_tokens"
                elif "max_output_tokens" in upstream_payload:
                    token_key = "max_output_tokens"
                else:
                    token_key = "max_tokens"

                requested = upstream_payload.get(token_key)
                if requested is None:
                    upstream_payload[token_key] = max_out
                elif isinstance(requested, int):
                    upstream_payload[token_key] = max(1, min(int(requested), max_out))

                for other_key in ("max_tokens", "max_completion_tokens", "max_output_tokens"):
                    if other_key != token_key:
                        upstream_payload.pop(other_key, None)

            estimated_input = (
                _estimate_chat_input_tokens(upstream_payload)
                if request_kind in {"chat", "responses"}
                else _estimate_embedding_input_tokens(upstream_payload)
            )
            reserved_tokens = int(max(0, estimated_input))
            allowed, reason = _rate_limit_check_and_record(
                self.conn,
                pg_conn=self.pg_conn,
                provider=target.provider,
                model=target.model,
                tz_name=self.settings.report_timezone,
                limits=model_limits,
                tokens=reserved_tokens,
            )
            if not allowed:
                status_code = 429
                error_code = "rate_limited"
                error_message = reason or "rate limited"
                response_json = {"error": {"code": error_code, "message": error_message}}
                response_text = error_message
                response_payload_capture = _build_payload_capture(
                    self.settings.capture_payloads,
                    response_json,
                )
                # Skip upstream call entirely.
                return ProxyResult(status_code=status_code, body=response_json)

            if stream_requested:
                if upstream.provider == "google" and upstream.auth_mode == "x-goog-api-key":
                    # Gemini native endpoints do not speak OpenAI SSE; we do a non-stream call upstream
                    # and wrap the final response into a minimal SSE stream for OpenClaw.
                    upstream_payload["stream"] = False
                    upstream_url, request_body = _build_google_native_request(
                        request_kind=request_kind,
                        base_url=upstream.base_url,
                        model=upstream.upstream_model,
                        payload=upstream_payload,
                    )
                    async with httpx.AsyncClient(timeout=self.settings.proxy_timeout_seconds) as client:
                        response = await client.post(
                            upstream_url,
                            headers=request_headers,
                            json=request_body,
                        )
                    status_code = response.status_code
                    try:
                        response_json = response.json()
                    except Exception:
                        response_json = {"error": {"code": f"http_{status_code}", "message": response.text}}
                    if status_code < 400 and isinstance(response_json, dict):
                        response_json = _translate_google_native_response(
                            request_kind=request_kind,
                            model=upstream.upstream_model,
                            response_json=response_json,
                        )
                    response_text = _extract_response_text(response_json)
                    response_payload_capture = _build_payload_capture(
                        self.settings.capture_payloads,
                        response_json,
                    )
                    if isinstance(response_json, dict):
                        response_id = response_json.get("id")
                        usage = response_json.get("usage") or {}
                        if isinstance(usage, dict) and usage:
                            input_tokens = usage.get("prompt_tokens") or usage.get("input_tokens")
                            output_tokens = usage.get("completion_tokens") or usage.get("output_tokens")
                            total_tokens = usage.get("total_tokens")
                            if (
                                input_tokens is not None
                                or output_tokens is not None
                                or total_tokens is not None
                            ):
                                token_accuracy = "exact"
                    if status_code >= 400:
                        error_code, error_message = _extract_error_details(
                            status_code=status_code,
                            response_json=response_json,
                            response_text=response.text,
                        )
                        _maybe_learn_model_limits(
                            self.conn,
                            provider=target.provider,
                            model=target.model,
                            http_status=status_code,
                            error_code=error_code,
                            error_message=error_message,
                        )
                        return ProxyResult(status_code=status_code, body=response_json)

                    telemetry_deferred = True
                    created_at = int(started_at.timestamp())
                    stream_id = str(response_id or f"stream-{uuid.uuid4().hex}")
                    model_name = str(upstream.upstream_model or upstream_payload.get("model") or "")
                    content_text = ""
                    if isinstance(response_json, dict):
                        choices = response_json.get("choices") or []
                        if isinstance(choices, list) and choices:
                            message = choices[0].get("message") if isinstance(choices[0], dict) else None
                            if isinstance(message, dict):
                                content_text = str(message.get("content") or "")

                    chunk_start = {
                        "id": stream_id,
                        "object": "chat.completion.chunk",
                        "created": created_at,
                        "model": model_name,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"role": "assistant", "content": content_text},
                                "finish_reason": None,
                            }
                        ],
                    }
                    chunk_end = {
                        "id": stream_id,
                        "object": "chat.completion.chunk",
                        "created": created_at,
                        "model": model_name,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {},
                                "finish_reason": "stop",
                            }
                        ],
                    }

                    async def iterator() -> AsyncIterator[bytes]:
                        try:
                            yield f"data: {_safe_json_dumps(chunk_start)}\n\n".encode("utf-8")
                            yield f"data: {_safe_json_dumps(chunk_end)}\n\n".encode("utf-8")
                            yield b"data: [DONE]\n\n"
                        finally:
                            output_estimated = _rough_token_estimate(response_text)
                            if status_code < 400 and request_kind in {"chat", "responses"} and model_limits:
                                if output_estimated > 0:
                                    _rate_limit_add_tokens(
                                        self.conn,
                                        pg_conn=self.pg_conn,
                                        provider=target.provider,
                                        model=target.model,
                                        tz_name=self.settings.report_timezone,
                                        limits=model_limits,
                                        tokens=output_estimated,
                                    )
                            final_input_tokens = input_tokens
                            final_output_tokens = output_tokens
                            final_total_tokens = total_tokens
                            final_token_accuracy = token_accuracy
                            if token_accuracy != "exact":
                                final_input_tokens = reserved_tokens
                                final_output_tokens = output_estimated
                                final_total_tokens = (final_input_tokens or 0) + (final_output_tokens or 0)
                                final_token_accuracy = (
                                    "estimated" if final_total_tokens > 0 else "unavailable"
                                )
                            elapsed_ms = int(
                                (datetime.now(timezone.utc) - started_at).total_seconds() * 1000
                            )
                            self._record(
                                UsageEvent(
                                    timestamp=started_at,
                                    service=service,
                                    provider=target.provider,
                                    model=target.model,
                                    request_kind=request_kind,
                                    success=True,
                                    http_status=status_code,
                                    latency_ms=elapsed_ms,
                                    attempt_number=1,
                                    input_tokens=final_input_tokens,
                                    output_tokens=final_output_tokens,
                                    total_tokens=final_total_tokens,
                                    token_accuracy=final_token_accuracy,
                                    input_chars=len(request_text),
                                    input_words=_word_count(request_text),
                                    input_estimated_tokens=_rough_token_estimate(request_text),
                                    response_chars=len(response_text),
                                    response_words=_word_count(response_text),
                                    response_estimated_tokens=_rough_token_estimate(response_text),
                                    request_payload=request_payload_capture,
                                    response_payload=response_payload_capture,
                                    origin_type=origin_type,
                                    origin_name=origin_name,
                                    trigger_type=trigger_type,
                                    trigger_name=trigger_name,
                                    agent_name=agent_name,
                                    error_code=None,
                                    error_message=None,
                                    request_id=response_id,
                                    logical_request_id=logical_request_id,
                                ),
                            )

                    return ProxyStreamResult(
                        status_code=200,
                        iterator=iterator(),
                        headers={
                            "Cache-Control": "no-cache",
                            "Connection": "keep-alive",
                        },
                    )

                upstream_url = _join_upstream_url(upstream.base_url, request_path)
                request_body = upstream_payload
                client = httpx.AsyncClient(timeout=self.settings.proxy_timeout_seconds)
                stream_cm = client.stream(
                    "POST",
                    upstream_url,
                    headers=request_headers,
                    json=request_body,
                )
                response = await stream_cm.__aenter__()
                status_code = response.status_code
                if status_code >= 400:
                    body_bytes = await response.aread()
                    response_text = body_bytes.decode("utf-8", errors="replace")
                    await stream_cm.__aexit__(None, None, None)
                    await client.aclose()
                    try:
                        response_json = json.loads(response_text)
                    except Exception:
                        response_json = {"error": {"code": f"http_{status_code}", "message": response_text}}
                    response_payload_capture = _build_payload_capture(
                        self.settings.capture_payloads,
                        response_json,
                    )
                    error_code, error_message = _extract_error_details(
                        status_code=status_code,
                        response_json=response_json,
                        response_text=response_text,
                    )
                    return ProxyResult(status_code=status_code, body=response_json)

                telemetry_deferred = True
                capture_mode = self.settings.capture_payloads
                preview_limit = 4000
                parse_buffer = b""
                preview_buffer = b""
                output_chunks: list[str] = []
                streamed_response_id: str | None = None
                streamed_error_code: str | None = None
                streamed_error_message: str | None = None

                async def iterator() -> AsyncIterator[bytes]:
                    nonlocal parse_buffer, preview_buffer, streamed_response_id, streamed_error_code, streamed_error_message
                    try:
                        async for chunk in response.aiter_bytes():
                            if capture_mode != "off" and len(preview_buffer) < preview_limit:
                                remaining = preview_limit - len(preview_buffer)
                                if remaining > 0:
                                    preview_buffer += chunk[:remaining]

                            parse_buffer += chunk
                            while b"\n" in parse_buffer:
                                line, parse_buffer = parse_buffer.split(b"\n", 1)
                                stripped = line.strip()
                                if not stripped:
                                    continue
                                if not stripped.startswith(b"data:"):
                                    continue
                                data = stripped[len(b"data:") :].strip()
                                if not data or data == b"[DONE]":
                                    continue
                                try:
                                    event = json.loads(data.decode("utf-8"))
                                except Exception:
                                    continue
                                if isinstance(event, dict):
                                    if not streamed_response_id and event.get("id"):
                                        streamed_response_id = str(event.get("id"))
                                    choices = event.get("choices")
                                    if isinstance(choices, list):
                                        for choice in choices:
                                            if not isinstance(choice, dict):
                                                continue
                                            delta = choice.get("delta") or {}
                                            if not isinstance(delta, dict):
                                                continue
                                            content = delta.get("content")
                                            if isinstance(content, str) and content:
                                                output_chunks.append(content)
                            yield chunk
                    except Exception as exc:  # pragma: no cover - streaming failure depends on transport
                        streamed_error_code = "upstream_error"
                        streamed_error_message = str(exc)
                        raise
                    finally:
                        try:
                            await stream_cm.__aexit__(None, None, None)
                        finally:
                            await client.aclose()

                        output_text = "".join(output_chunks)
                        output_estimated = _rough_token_estimate(output_text)
                        if status_code < 400 and request_kind in {"chat", "responses"} and model_limits:
                            if output_estimated > 0:
                                _rate_limit_add_tokens(
                                    self.conn,
                                        pg_conn=self.pg_conn,
                                    provider=target.provider,
                                    model=target.model,
                                    tz_name=self.settings.report_timezone,
                                    limits=model_limits,
                                    tokens=output_estimated,
                                )

                        response_payload = None
                        if capture_mode != "off":
                            preview_text = preview_buffer.decode("utf-8", errors="replace")
                            response_payload = _build_payload_capture(
                                capture_mode,
                                {"sse_preview": preview_text},
                            )
                        elapsed_ms = int(
                            (datetime.now(timezone.utc) - started_at).total_seconds() * 1000
                        )
                        self._record(
                            UsageEvent(
                                timestamp=started_at,
                                service=service,
                                provider=target.provider,
                                model=target.model,
                                request_kind=request_kind,
                                success=streamed_error_code is None,
                                http_status=status_code,
                                latency_ms=elapsed_ms,
                                attempt_number=1,
                                input_tokens=reserved_tokens,
                                output_tokens=output_estimated,
                                total_tokens=reserved_tokens + output_estimated,
                                token_accuracy="estimated"
                                if (reserved_tokens + output_estimated) > 0
                                else "unavailable",
                                input_chars=len(request_text),
                                input_words=_word_count(request_text),
                                input_estimated_tokens=_rough_token_estimate(request_text),
                                response_chars=len(output_text),
                                response_words=_word_count(output_text),
                                response_estimated_tokens=_rough_token_estimate(output_text),
                                request_payload=request_payload_capture,
                                response_payload=response_payload,
                                origin_type=origin_type,
                                origin_name=origin_name,
                                trigger_type=trigger_type,
                                trigger_name=trigger_name,
                                agent_name=agent_name,
                                error_code=streamed_error_code,
                                error_message=streamed_error_message,
                                request_id=streamed_response_id,
                                logical_request_id=logical_request_id,
                            ),
                        )
                        if streamed_error_code and streamed_error_message:
                            _maybe_learn_model_limits(
                                self.conn,
                                provider=target.provider,
                                model=target.model,
                                http_status=status_code,
                                error_code=streamed_error_code,
                                error_message=streamed_error_message,
                            )

                return ProxyStreamResult(
                    status_code=status_code,
                    iterator=iterator(),
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                    },
                )

            if upstream.provider == "google" and upstream.auth_mode == "x-goog-api-key":
                upstream_url, request_body = _build_google_native_request(
                    request_kind=request_kind,
                    base_url=upstream.base_url,
                    model=upstream.upstream_model,
                    payload=upstream_payload,
                )
            else:
                upstream_url = _join_upstream_url(upstream.base_url, request_path)
                request_body = upstream_payload
            async with httpx.AsyncClient(timeout=self.settings.proxy_timeout_seconds) as client:
                response = await client.post(
                    upstream_url,
                    headers=request_headers,
                    json=request_body,
                )
            status_code = response.status_code
            try:
                response_json = response.json()
            except Exception:
                # Non-JSON response (or invalid JSON); preserve text for debugging.
                response_json = {"error": {"code": f"http_{status_code}", "message": response.text}}

            if (
                upstream.provider == "google"
                and upstream.auth_mode == "x-goog-api-key"
                and status_code < 400
                and isinstance(response_json, dict)
            ):
                response_json = _translate_google_native_response(
                    request_kind=request_kind,
                    model=upstream.upstream_model,
                    response_json=response_json,
                )
            response_text = _extract_response_text(response_json)
            response_payload_capture = _build_payload_capture(
                self.settings.capture_payloads,
                response_json,
            )
            if status_code < 400 and request_kind in {"chat", "responses"} and model_limits:
                extra_output_tokens = _estimate_chat_output_tokens(response_json)
                if extra_output_tokens > 0:
                    _rate_limit_add_tokens(
                        self.conn,
                                        pg_conn=self.pg_conn,
                        provider=target.provider,
                        model=target.model,
                        tz_name=self.settings.report_timezone,
                        limits=model_limits,
                        tokens=extra_output_tokens,
                    )

            if isinstance(response_json, dict):
                response_id = response_json.get("id")
                usage = response_json.get("usage") or {}
                if isinstance(usage, dict) and usage:
                    input_tokens = usage.get("prompt_tokens") or usage.get("input_tokens")
                    output_tokens = usage.get("completion_tokens") or usage.get("output_tokens")
                    total_tokens = usage.get("total_tokens")
                    if input_tokens is not None or output_tokens is not None or total_tokens is not None:
                        token_accuracy = "exact"
            if (
                token_accuracy != "exact"
                and self.settings.estimate_chat_tokens
                and request_kind in {"chat", "responses"}
                and status_code < 400
            ):
                input_tokens = _estimate_chat_input_tokens(sanitized_payload)
                output_tokens = _estimate_chat_output_tokens(response_json)
                total_tokens = (input_tokens or 0) + (output_tokens or 0)
                token_accuracy = "estimated" if total_tokens > 0 else "unavailable"
            if token_accuracy != "exact" and request_kind == "embedding":
                input_tokens = _estimate_embedding_input_tokens(payload)
                output_tokens = 0
                total_tokens = input_tokens
                token_accuracy = "estimated" if input_tokens > 0 else "unavailable"
            if status_code >= 400:
                error_code, error_message = _extract_error_details(
                    status_code=status_code,
                    response_json=response_json,
                    response_text=response.text,
                )
                _maybe_learn_model_limits(
                    self.conn,
                    provider=target.provider,
                    model=target.model,
                    http_status=status_code,
                    error_code=error_code,
                    error_message=error_message,
                )
        except httpx.TimeoutException as exc:
            status_code = 504
            error_code = "timeout"
            error_message = str(exc)
            response_json = {"error": {"code": error_code, "message": error_message}}
            response_text = error_message
            response_payload_capture = _build_payload_capture(
                self.settings.capture_payloads,
                response_json,
            )
        except Exception as exc:  # pragma: no cover - safety net
            status_code = 502
            error_code = "upstream_error"
            error_message = str(exc)
            response_json = {"error": {"code": error_code, "message": error_message}}
            response_text = error_message
            response_payload_capture = _build_payload_capture(
                self.settings.capture_payloads,
                response_json,
            )
        finally:
            if not telemetry_deferred:
                if error_code and error_message:
                    _maybe_learn_model_limits(
                        self.conn,
                        provider=target.provider,
                        model=target.model,
                        http_status=status_code,
                        error_code=str(error_code),
                        error_message=str(error_message),
                    )
                elapsed_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)
                self._record(
                    UsageEvent(
                        timestamp=started_at,
                        service=service,
                        provider=target.provider,
                        model=target.model,
                        request_kind=request_kind,
                        success=200 <= status_code < 400,
                        http_status=status_code,
                        latency_ms=elapsed_ms,
                        attempt_number=1,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        total_tokens=total_tokens,
                        token_accuracy=token_accuracy,
                        input_chars=len(request_text),
                        input_words=_word_count(request_text),
                        input_estimated_tokens=_rough_token_estimate(request_text),
                        response_chars=len(response_text),
                        response_words=_word_count(response_text),
                        response_estimated_tokens=_rough_token_estimate(response_text),
                        request_payload=request_payload_capture,
                        response_payload=response_payload_capture,
                        origin_type=origin_type,
                        origin_name=origin_name,
                        trigger_type=trigger_type,
                        trigger_name=trigger_name,
                        agent_name=agent_name,
                        error_code=error_code,
                        error_message=error_message,
                        request_id=response_id,
                        logical_request_id=logical_request_id,
                    ),
                )

        return ProxyResult(status_code=status_code, body=response_json)
