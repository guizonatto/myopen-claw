"""
Tool: Discord Notify
Envia mensagens para um canal Discord via OpenClaw Gateway.
Requer que o canal Discord esteja habilitado e o bot configurado.
"""
import os
import requests

DISCORD_CHANNEL_ID = os.getenv("DISCORD_ZIND_CONTENT_CHANNEL_ID")
GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:18789")


def send_discord_message(content: str, channel_id: str = None) -> bool:
    """Envia uma mensagem para um canal Discord via OpenClaw Gateway REST API."""
    channel = channel_id or DISCORD_CHANNEL_ID
    if not channel:
        raise ValueError("DISCORD_ZIND_CONTENT_CHANNEL_ID não configurado.")
    payload = {
        "channel": "discord",
        "to": f"channel:{channel}",
        "content": content
    }
    resp = requests.post(f"{GATEWAY_URL}/api/message", json=payload)
    return resp.status_code == 200

# Exemplo de uso
if __name__ == "__main__":
    msg = "Testando envio para Discord via tool Python."
    ok = send_discord_message(msg)
    print("Enviado com sucesso!" if ok else "Falha ao enviar.")

# Receber mensagens do Discord normalmente depende de webhook/evento do Gateway.
# Consulte a doc do OpenClaw para integração de recebimento.
