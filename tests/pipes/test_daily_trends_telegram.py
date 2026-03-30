"""
Testes para pipes/daily_trends_report_telegram.py
"""
from unittest.mock import patch, MagicMock


def test_run_orchestrates_skill_and_tool():
    """run() deve chamar a skill de trends e a tool de notificação."""
    with patch("pipes.daily_trends_report_telegram.summarize_trends") as mock_skill, \
         patch("pipes.daily_trends_report_telegram.telegram_notify") as mock_tool:

        mock_skill.run.return_value = "resumo dos trends"

        from pipes.daily_trends_report_telegram import run
        run()

        assert mock_skill.run.called
        assert mock_tool.send.called
