"""
Script: send_to_discord.py
Função: Envia relatório para Discord criando uma thread por execução
Usar quando: Publicar relatório semanal no Discord

ENV_VARS:
  - DISCORD_BOT_TOKEN: token do bot Discord
  - DISCORD_GUILD_ID: ID do servidor Discord
  - DISCORD_CHANNEL_ID: (opcional) ID direto do canal

DB_TABLES:
  - (nenhuma)
"""
import os
import time
import requests

_PREFERRED_CHANNEL_KEYWORDS = [
    "weekly-report", "weekly_report", "entregas", "entrega",
    "releases", "release", "changelog", "projetos", "projeto",
    "avisos", "aviso",
]


def _pick_channel(channels):
    text = [c for c in channels if c.get("type") == 0]
    if not text:
        raise Exception("Nenhum canal de texto encontrado no servidor Discord.")
    for keyword in _PREFERRED_CHANNEL_KEYWORDS:
        for c in text:
            parts = (c.get("name") or "").lower().replace("-", " ").replace("_", " ").split()
            if keyword.replace("-", " ").replace("_", " ") in " ".join(parts):
                return c["id"]
    return text[0]["id"]


def _split_message(text, limit=1900):
    if len(text) <= limit:
        return [text]
    parts = []
    current = []
    current_len = 0
    for line in text.splitlines(keepends=True):
        if current_len + len(line) > limit and current:
            parts.append("".join(current))
            current = []
            current_len = 0
        current.append(line)
        current_len += len(line)
    if current:
        parts.append("".join(current))
    return parts


def _post(url, headers, content):
    """Envia um chunk de texto com retry em rate limit."""
    for attempt in range(3):
        resp = requests.post(url, headers=headers, json={"content": content}, timeout=15)
        if resp.status_code == 429:
            retry_after = float(resp.json().get("retry_after", 1.5))
            time.sleep(retry_after)
            continue
        resp.raise_for_status()
        time.sleep(0.6)   # respeita 5 msg/5s do Discord
        return resp.json()
    resp.raise_for_status()
    return resp.json()


def send_to_discord(content, channel_id=None, thread_title=None):
    """
    Envia uma ou mais mensagens para o Discord.

    Se thread_title for informado:
      - Primeira mensagem vai para o canal como abertura da thread
      - Thread é criada a partir dessa mensagem
      - Todo o restante vai dentro da thread

    content: str ou list[str]
    thread_title: str — título da thread (ex: "Weekly Report — W17 2026-04-25")
    """
    token = os.getenv("DISCORD_BOT_TOKEN")
    guild_id = os.getenv("DISCORD_GUILD_ID")
    if not token or not guild_id:
        raise Exception("DISCORD_BOT_TOKEN e DISCORD_GUILD_ID obrigatórios")

    headers = {
        "Authorization": f"Bot {token}",
        "Content-Type": "application/json",
    }

    if not channel_id:
        channel_id = os.getenv("DISCORD_CHANNEL_ID")
    if not channel_id:
        resp = requests.get(
            f"https://discord.com/api/v10/guilds/{guild_id}/channels",
            headers=headers, timeout=15,
        )
        resp.raise_for_status()
        channel_id = _pick_channel(resp.json())

    parts = content if isinstance(content, list) else [content]
    parts = [p for p in parts if p and p.strip()]

    if not parts:
        return {}

    channel_url = f"https://discord.com/api/v10/channels/{channel_id}/messages"

    if not thread_title:
        # Sem thread — envia tudo no canal normalmente
        last = {}
        for part in parts:
            for chunk in _split_message(part.strip()):
                last = _post(channel_url, headers, chunk)
        return last

    # ── Modo thread ──────────────────────────────────────────────
    # 1. Posta primeira parte no canal (cabeçalho que vira a thread)
    first_chunks = _split_message(parts[0].strip())
    opener = _post(channel_url, headers, first_chunks[0])
    opener_id = opener["id"]

    # 2. Cria a thread a partir da mensagem de abertura
    thread_resp = requests.post(
        f"https://discord.com/api/v10/channels/{channel_id}/messages/{opener_id}/threads",
        headers=headers,
        json={"name": thread_title[:100], "auto_archive_duration": 10080},
        timeout=15,
    )
    thread_resp.raise_for_status()
    thread_id = thread_resp.json()["id"]
    thread_url = f"https://discord.com/api/v10/channels/{thread_id}/messages"

    # 3. Chunks restantes da primeira parte → thread
    last = opener
    for chunk in first_chunks[1:]:
        last = _post(thread_url, headers, chunk)

    # 4. Demais partes → thread
    for part in parts[1:]:
        for chunk in _split_message(part.strip()):
            last = _post(thread_url, headers, chunk)

    return last


if __name__ == "__main__":
    print(send_to_discord("Teste de envio — Weekly Report", thread_title="Teste Thread"))
