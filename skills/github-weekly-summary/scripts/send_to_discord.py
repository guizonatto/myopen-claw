"""
Envia resumo para canal Discord.
Requer: DISCORD_BOT_TOKEN, DISCORD_GUILD_ID
O script deve buscar os canais do servidor (guild) e permitir escolher o canal mais adequado para o tipo de mensagem.
"""
import os
import requests

def send_to_discord(message, channel_id=None):
    token = os.getenv("DISCORD_BOT_TOKEN")
    guild_id = os.getenv("DISCORD_GUILD_ID")
    if not token or not guild_id:
        raise Exception("DISCORD_BOT_TOKEN e DISCORD_GUILD_ID obrigatórios")
    # Buscar canais do servidor
    url_channels = f"https://discord.com/api/v10/guilds/{guild_id}/channels"
    headers = {
        "Authorization": f"Bot {token}",
        "Content-Type": "application/json"
    }
    resp_channels = requests.get(url_channels, headers=headers)
    resp_channels.raise_for_status()
    channels = resp_channels.json()
    # Selecionar canal coerente (exemplo: primeiro canal de texto)
    if not channel_id:
        text_channels = [c for c in channels if c["type"] == 0]
        if not text_channels:
            raise Exception("Nenhum canal de texto encontrado no servidor Discord.")
        channel_id = text_channels[0]["id"]
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
    data = {"content": message}
    resp = requests.post(url, headers=headers, json=data)
    resp.raise_for_status()
    return resp.json()

if __name__ == "__main__":
    print(send_to_discord("Release semanal publicada!"))
