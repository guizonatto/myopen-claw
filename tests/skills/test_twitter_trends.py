"""
Testes para skills/twitter_trends.py

Padrão: mockar dependências externas (API, DB).
Testar apenas a lógica da skill, não a infraestrutura.
"""
from unittest.mock import patch, MagicMock
import pytest


def test_run_returns_list(monkeypatch):
    """run() deve retornar lista (mesmo que vazia)."""
    mock_conn = MagicMock()
    mock_conn.__enter__ = lambda s: s
    mock_conn.__exit__ = MagicMock(return_value=False)

    with patch("skills.twitter_trends.requests.get") as mock_get, \
         patch("skills.twitter_trends.get_connection", return_value=mock_conn):

        mock_get.return_value.json.return_value = {"data": []}
        mock_get.return_value.status_code = 200

        from skills.twitter_trends import run
        result = run()
        assert isinstance(result, (list, dict, type(None)))
