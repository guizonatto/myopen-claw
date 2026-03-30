"""
Testes para tools/telegram_notify.py
"""
from unittest.mock import patch, MagicMock


def test_send_calls_telegram_api():
    """send() deve chamar a API do Telegram com a mensagem correta."""
    with patch("tools.telegram_notify.requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"ok": True}

        from tools.telegram_notify import send
        send("mensagem de teste")

        assert mock_post.called
        call_kwargs = mock_post.call_args
        assert "mensagem de teste" in str(call_kwargs)


def test_send_does_not_raise_on_error():
    """send() não deve lançar exceção se a API falhar."""
    with patch("tools.telegram_notify.requests.post") as mock_post:
        mock_post.side_effect = Exception("connection refused")

        from tools.telegram_notify import send
        try:
            send("teste")
        except Exception:
            assert False, "send() não deve propagar exceções"
