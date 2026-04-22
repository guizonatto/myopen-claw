"""
Tool: dispatcher
Função: Calcula janelas horárias, gera relatório consolidado e faz dispatch idempotente ao gateway.
Usar quando: Precisar enviar o relatório horário de uso de modelos sem envolver LLM.

ENV_VARS:
  - OPENCLAW_GATEWAY_URL: URL base do gateway
  - OPENCLAW_GATEWAY_TOKEN: token opcional para o gateway
  - MODEL_USAGE_REPORT_DISCORD_CHANNEL_ID: canal Discord de destino
  - MODEL_USAGE_REPORT_TIMEZONE: timezone operacional do relatório

DB_TABLES:
  - usage_events: leitura
  - report_dispatches: leitura+escrita
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx

from llm_usage_telemetry.reporting import build_discord_report
from llm_usage_telemetry.settings import TelemetrySettings
from llm_usage_telemetry.storage import (
    connect_db,
    initialize_schema,
    mark_report_dispatched,
    summarize_usage,
    was_report_dispatched,
)
from llm_usage_telemetry.reporting import ProviderSummary

DISCORD_MESSAGE_LIMIT = 1900


@dataclass(slots=True)
class ReportingWindows:
    bucket_start_utc: datetime
    bucket_end_utc: datetime
    day_start_utc: datetime
    bucket_label: str


def build_reporting_windows(now_utc: datetime, timezone_name: str) -> ReportingWindows:
    zone = ZoneInfo(timezone_name)
    local_now = now_utc.astimezone(zone)
    bucket_end_local = local_now.replace(minute=0, second=0, microsecond=0)
    bucket_start_local = bucket_end_local - timedelta(hours=1)
    day_start_local = bucket_start_local.replace(hour=0, minute=0, second=0, microsecond=0)
    return ReportingWindows(
        bucket_start_utc=bucket_start_local.astimezone(timezone.utc),
        bucket_end_utc=bucket_end_local.astimezone(timezone.utc),
        day_start_utc=day_start_local.astimezone(timezone.utc),
        bucket_label=(
            f"{bucket_start_local:%Y-%m-%d} "
            f"{bucket_start_local:%H}:00-{bucket_start_local:%H}:59"
        ),
    )


async def _send_gateway_message(settings: TelemetrySettings, content: str) -> bool:
    if not settings.discord_channel_id:
        return False

    chunks = _split_discord_content(content, limit=DISCORD_MESSAGE_LIMIT)

    if settings.discord_bot_token:
        async with httpx.AsyncClient(timeout=30) as client:
            for chunk in chunks:
                discord_response = await client.post(
                    f"https://discord.com/api/v10/channels/{settings.discord_channel_id}/messages",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bot {settings.discord_bot_token}",
                    },
                    json={"content": chunk},
                )
                if discord_response.status_code not in {200, 201}:
                    break
            else:
                return True

    base_headers = {"Content-Type": "application/json"}
    auth_secrets: list[str] = []
    for secret in (settings.gateway_password, settings.gateway_token):
        if secret and secret not in auth_secrets:
            auth_secrets.append(secret)
    if not auth_secrets:
        auth_secrets.append("")

    async with httpx.AsyncClient(timeout=30) as client:
        base_url = settings.gateway_url.rstrip("/")
        target = f"channel:{settings.discord_channel_id}"
        for secret in auth_secrets:
            headers = dict(base_headers)
            if secret:
                headers["Authorization"] = f"Bearer {secret}"

            # Current OpenClaw gateways expose outbound delivery through the message tool.
            responses = [
                await client.post(
                    f"{base_url}/tools/invoke",
                    headers=headers,
                    json={
                        "tool": "message",
                        "action": "send",
                        "args": {
                            "channel": "discord",
                            "target": target,
                            "message": chunk,
                        },
                        "sessionKey": "main",
                    },
                )
                for chunk in chunks
            ]
            if all(response.status_code == 200 for response in responses):
                return True
            if any(response.status_code == 401 for response in responses):
                continue

            # Keep a legacy fallback for older gateway builds that exposed /api/message.
            if any(response.status_code in {404, 405} for response in responses):
                legacy_responses = [
                    await client.post(
                        f"{base_url}/api/message",
                        headers=headers,
                        json={
                            "channel": "discord",
                            "to": target,
                            "content": chunk,
                        },
                    )
                    for chunk in chunks
                ]
                if all(response.status_code == 200 for response in legacy_responses):
                    return True

    return False


def _split_discord_content(content: str, limit: int = DISCORD_MESSAGE_LIMIT) -> list[str]:
    if len(content) <= limit:
        return [content]

    chunks: list[str] = []
    current_lines: list[str] = []
    current_length = 0
    for line in content.splitlines():
        line_length = len(line) + (1 if current_lines else 0)
        if current_lines and current_length + line_length > limit:
            chunks.append("\n".join(current_lines))
            current_lines = [line]
            current_length = len(line)
            continue

        if len(line) > limit:
            if current_lines:
                chunks.append("\n".join(current_lines))
                current_lines = []
                current_length = 0
            for start in range(0, len(line), limit):
                chunks.append(line[start : start + limit])
            continue

        current_lines.append(line)
        current_length += line_length

    if current_lines:
        chunks.append("\n".join(current_lines))

    return chunks or [content[:limit]]


async def dispatch_hourly_report(
    settings: TelemetrySettings,
    now_utc: datetime | None = None,
) -> bool:
    current_time = now_utc or datetime.now(timezone.utc)
    windows = build_reporting_windows(current_time, settings.report_timezone)
    conn = connect_db(settings.db_path)
    initialize_schema(conn)

    try:
        if was_report_dispatched(
            conn,
            report_key="hourly-discord",
            bucket_start=windows.bucket_start_utc,
            channel="discord",
            target=f"channel:{settings.discord_channel_id}",
        ):
            return False

        last_hour_rows = summarize_usage(
            conn,
            start_at=windows.bucket_start_utc,
            end_at=windows.bucket_end_utc,
        )
        day_rows = summarize_usage(
            conn,
            start_at=windows.day_start_utc,
            end_at=windows.bucket_end_utc,
        )

        day_bucket_start = windows.day_start_utc.isoformat()
        provider_counts = {
            row["provider"]: (int(row["enabled_models"] or 0), int(row["total_models"] or 0))
            for row in conn.execute(
                """
                SELECT
                  provider,
                  SUM(CASE WHEN enabled = 1 THEN 1 ELSE 0 END) AS enabled_models,
                  COUNT(*) AS total_models
                FROM model_limits
                GROUP BY provider
                """
            ).fetchall()
        }
        provider_usage = {
            row["provider"]: (int(row["requests"] or 0), int(row["tokens"] or 0))
            for row in conn.execute(
                """
                SELECT provider, SUM(requests) AS requests, SUM(tokens) AS tokens
                FROM model_rate_buckets
                WHERE bucket_kind = 'day' AND bucket_start = ?
                GROUP BY provider
                """,
                (day_bucket_start,),
            ).fetchall()
        }
        provider_summaries = []
        for provider, (enabled_models, total_models) in sorted(provider_counts.items()):
            provider_summaries.append(
                ProviderSummary(
                    provider=provider,
                    enabled_models=enabled_models,
                    total_models=total_models,
                    day_requests=provider_usage.get(provider, (0, 0))[0],
                    day_tokens=provider_usage.get(provider, (0, 0))[1],
                )
            )

        active_models = {
            (row.provider, row.model) for row in (last_hour_rows + day_rows) if row.provider and row.model
        }
        model_limits: dict[tuple[str, str], dict[str, int | None]] = {}
        if active_models:
            limits_rows = conn.execute(
                """
                SELECT provider, model, rpm, rpd, tpm, tpd
                FROM model_limits
                WHERE provider IS NOT NULL AND model IS NOT NULL
                """
            ).fetchall()
            for row in limits_rows:
                key = (row["provider"], row["model"])
                if key not in active_models:
                    continue
                model_limits[key] = {
                    "rpm": row["rpm"],
                    "rpd": row["rpd"],
                    "tpm": row["tpm"],
                    "tpd": row["tpd"],
                }

        day_usage: dict[tuple[str, str], tuple[int, int]] = {}
        if active_models:
            usage_rows = conn.execute(
                """
                SELECT provider, model, requests, tokens
                FROM model_rate_buckets
                WHERE bucket_kind = 'day' AND bucket_start = ?
                """,
                (day_bucket_start,),
            ).fetchall()
            for row in usage_rows:
                key = (row["provider"], row["model"])
                if key not in active_models:
                    continue
                day_usage[key] = (int(row["requests"] or 0), int(row["tokens"] or 0))
        content = build_discord_report(
            last_hour_rows=last_hour_rows,
            day_rows=day_rows,
            timezone_name=settings.report_timezone,
            bucket_label=windows.bucket_label,
            provider_summaries=provider_summaries,
            model_limits=model_limits,
            day_usage=day_usage,
        )

        if not await _send_gateway_message(settings, content):
            return False

        mark_report_dispatched(
            conn,
            report_key="hourly-discord",
            bucket_start=windows.bucket_start_utc,
            channel="discord",
            target=f"channel:{settings.discord_channel_id}",
        )
        return True
    finally:
        conn.close()
