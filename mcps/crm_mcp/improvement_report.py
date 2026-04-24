from __future__ import annotations

import os
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

try:
    from .message_strategy import build_daily_improvement_snapshot, render_daily_improvement_report, split_discord_content
except ImportError:  # pragma: no cover
    from message_strategy import build_daily_improvement_snapshot, render_daily_improvement_report, split_discord_content


def _build_targets(channel_id: str | None, target: str | None) -> tuple[str | None, str]:
    env_channel = (os.environ.get("CRM_IMPROVEMENT_DISCORD_CHANNEL_ID") or "").strip()
    env_target = (os.environ.get("CRM_IMPROVEMENT_DISCORD_TARGET") or "").strip()

    effective_channel = (channel_id or env_channel or "").strip() or None
    if target:
        effective_target = target
    elif env_target:
        effective_target = env_target
    elif effective_channel:
        effective_target = f"channel:{effective_channel}"
    else:
        effective_target = "channel:sales-bot-improvement"
    return effective_channel, effective_target


def _is_due(now: datetime, *, timezone_name: str = "America/Sao_Paulo") -> bool:
    local = now.astimezone(ZoneInfo(timezone_name))
    return local.hour in {12, 19}


def _post_direct_discord(channel_id: str, content: str, bot_token: str) -> requests.Response:
    return requests.post(
        f"https://discord.com/api/v10/channels/{channel_id}/messages",
        headers={
            "Authorization": f"Bot {bot_token}",
            "Content-Type": "application/json",
        },
        json={"content": content},
        timeout=20,
    )


def _post_gateway(content: str, target: str, gateway_url: str, secret: str) -> requests.Response:
    headers = {"Content-Type": "application/json"}
    if secret:
        headers["Authorization"] = f"Bearer {secret}"
    return requests.post(
        f"{gateway_url.rstrip('/')}/tools/invoke",
        headers=headers,
        json={
            "tool": "message",
            "action": "send",
            "args": {
                "channel": "discord",
                "target": target,
                "message": content,
            },
            "sessionKey": "main",
        },
        timeout=20,
    )


def _post_gateway_legacy(content: str, target: str, gateway_url: str, secret: str) -> requests.Response:
    headers = {"Content-Type": "application/json"}
    if secret:
        headers["Authorization"] = f"Bearer {secret}"
    return requests.post(
        f"{gateway_url.rstrip('/')}/api/message",
        headers=headers,
        json={
            "channel": "discord",
            "to": target,
            "content": content,
        },
        timeout=20,
    )


def _send_chunks(chunks: list[str], *, channel_id: str | None, target: str) -> dict:
    bot_token = (os.environ.get("DISCORD_BOT_TOKEN") or "").strip()
    gateway_url = (os.environ.get("OPENCLAW_GATEWAY_URL") or os.environ.get("GATEWAY_URL") or "http://localhost:18789").strip()
    secrets = [
        secret.strip()
        for secret in (
            os.environ.get("OPENCLAW_GATEWAY_PASSWORD", ""),
            os.environ.get("OPENCLAW_GATEWAY_TOKEN", ""),
        )
        if secret and secret.strip()
    ]
    if not secrets:
        secrets = [""]

    if bot_token and channel_id:
        ok = True
        for chunk in chunks:
            response = _post_direct_discord(channel_id, chunk, bot_token)
            if response.status_code not in {200, 201}:
                ok = False
                break
        if ok:
            return {"sent": True, "mode": "direct_discord"}

    for secret in secrets:
        responses = [_post_gateway(chunk, target, gateway_url, secret) for chunk in chunks]
        if all(response.status_code == 200 for response in responses):
            return {"sent": True, "mode": "gateway_tools_invoke"}
        if any(response.status_code in {404, 405} for response in responses):
            legacy = [_post_gateway_legacy(chunk, target, gateway_url, secret) for chunk in chunks]
            if all(response.status_code == 200 for response in legacy):
                return {"sent": True, "mode": "gateway_legacy_api_message"}

    return {"sent": False, "mode": "failed"}


def send_daily_improvement_report(
    session,
    *,
    force: bool = False,
    channel_id: str | None = None,
    target: str | None = None,
    now: datetime | None = None,
) -> dict:
    current = now or datetime.now(tz=ZoneInfo("America/Sao_Paulo"))
    if not force and not _is_due(current):
        return {"skipped": True, "reason": "outside_schedule_window", "scheduled_hours_brt": [12, 19]}

    snapshot = build_daily_improvement_snapshot(session)
    content = render_daily_improvement_report(snapshot)
    chunks = split_discord_content(content)
    resolved_channel, resolved_target = _build_targets(channel_id, target)
    delivery = _send_chunks(chunks, channel_id=resolved_channel, target=resolved_target)

    return {
        "skipped": False,
        "delivered": bool(delivery.get("sent")),
        "delivery_mode": delivery.get("mode"),
        "channel_id": resolved_channel,
        "target": resolved_target,
        "chunks": len(chunks),
        "snapshot": snapshot,
        "content_preview": content[:400],
    }
