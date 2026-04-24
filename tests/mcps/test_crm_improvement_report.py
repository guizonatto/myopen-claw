from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from mcps.crm_mcp.improvement_report import send_daily_improvement_report
from mcps.crm_mcp.message_strategy import split_discord_content


def test_split_discord_content_preserves_text():
    content = "\n".join([f"linha-{idx}-{'x' * 40}" for idx in range(120)])
    chunks = split_discord_content(content, limit=300)

    assert len(chunks) > 1
    assert all(len(chunk) <= 300 for chunk in chunks)
    assert "\n".join(chunks) == content


def test_send_daily_improvement_report_skips_outside_schedule():
    now = datetime(2026, 4, 23, 10, 0, tzinfo=ZoneInfo("America/Sao_Paulo"))
    result = send_daily_improvement_report(
        session=object(),
        force=False,
        now=now,
    )

    assert result["skipped"] is True
    assert result["reason"] == "outside_schedule_window"


def test_send_daily_improvement_report_generates_and_chunks(monkeypatch):
    captured = {"chunks": 0}

    monkeypatch.setattr(
        "mcps.crm_mcp.improvement_report.build_daily_improvement_snapshot",
        lambda session: {
            "top_strategies": [],
            "bottom_strategies": [],
            "winners": [],
            "losers": [],
        },
    )
    monkeypatch.setattr(
        "mcps.crm_mcp.improvement_report.render_daily_improvement_report",
        lambda snapshot: "\n".join([f"linha {idx} - {'x' * 80}" for idx in range(180)]),
    )

    def _fake_send_chunks(chunks, *, channel_id, target):
        captured["chunks"] = len(chunks)
        return {"sent": True, "mode": "fake"}

    monkeypatch.setattr("mcps.crm_mcp.improvement_report._send_chunks", _fake_send_chunks)
    now = datetime(2026, 4, 23, 12, 0, tzinfo=ZoneInfo("America/Sao_Paulo"))
    result = send_daily_improvement_report(
        session=object(),
        force=True,
        now=now,
    )

    assert result["skipped"] is False
    assert result["delivered"] is True
    assert result["delivery_mode"] == "fake"
    assert captured["chunks"] > 1
