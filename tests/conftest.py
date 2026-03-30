"""
Fixtures compartilhadas para todos os testes do OpenClaw.

Uso:
  pytest tests/
  pytest tests/skills/
  pytest tests/skills/test_twitter_trends.py
"""
import os
import pytest


@pytest.fixture(autouse=True)
def env_defaults(monkeypatch):
    """Garante valores padrão para env vars em todos os testes."""
    defaults = {
        "DATABASE_URL": "postgresql://postgres:postgres@localhost:5432/openclaw_test",
        "ANTHROPIC_API_KEY": "test-key",
        "TWITTER_BEARER_TOKEN": "test-token",
        "TELEGRAM_BOT_TOKEN": "test-token",
        "TELEGRAM_CHAT_ID": "123456",
        "WHATSAPP_API_URL": "http://localhost",
        "WHATSAPP_TOKEN": "test-token",
        "WHATSAPP_TO": "+5500000000000",
    }
    for key, value in defaults.items():
        monkeypatch.setenv(key, os.environ.get(key, value))
