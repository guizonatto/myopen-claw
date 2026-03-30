import pytest
from skills.trends import summarize_trends

def test_run_skill():
    summary = summarize_trends.run()
    assert "Trending Topics do X" in summary
    assert "Resumo gerado automaticamente" in summary