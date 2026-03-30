import pytest
from skills.trends import fetch_trending_topics
import sys

class DummyCompletedProcess:
    def __init__(self, stdout):
        self.stdout = stdout


def test_run_success(monkeypatch):
    mock_output = """
# Trending
* OpenAI
* Python
* OpenClaw
* AI
* TechNews
"""
    def mock_run(*args, **kwargs):
        return DummyCompletedProcess(stdout=mock_output)
    monkeypatch.setattr(fetch_trending_topics.subprocess, "run", mock_run)
    topics = fetch_trending_topics.run(limit=3)
    assert topics == ["Trending", "OpenAI", "Python"]

def test_run_error(monkeypatch):
    def mock_run(*args, **kwargs):
        raise Exception("firecrawl not found")
    monkeypatch.setattr(fetch_trending_topics.subprocess, "run", mock_run)
    topics = fetch_trending_topics.run()
    assert any("Erro ao buscar" in t for t in topics)
