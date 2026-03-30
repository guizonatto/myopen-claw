import pytest
from pipes.trends import trending_topics_report

def test_run_pipe(monkeypatch):
    # Mock a skill e tool
    monkeypatch.setattr(trending_topics_report, "summarize_trends", lambda: "Resumo mockado")
    monkeypatch.setattr(trending_topics_report, "send_telegram_message", lambda msg: msg)
    result = trending_topics_report.run()
    assert result is None or result == "Resumo mockado"