# TOOLS.md — Ferramentas e Integrações

## Ferramentas da aplicação (tools/)

| Tool | Arquivo | Função |
|---|---|---|
| Telegram | `tools/telegram_notify.py` | Envio de mensagens via Bot API |
| WhatsApp | `tools/whatsapp_notify.py` | Envio via UltraMsg/Z-API |

## Ferramentas de infraestrutura

- **Poetry** — gerenciamento de dependências (`pyproject.toml` + `poetry.lock`)
- **PostgreSQL / pgvector** — banco de dados principal e memória do sistema
- **APScheduler** — agendamento de crons
- **Playwright** — scraping via browser com simulação humana
- **Docker + Watchtower** — deploy e atualização automática

## Variáveis de ambiente necessárias

Todas devem existir no `.env` (baseado no `.env.example`):

| Variável | Usada por |
|---|---|
| `DATABASE_URL` | `openclaw/memory_db.py` |
| `TWITTER_BEARER_TOKEN` | `skills/twitter_trends.py` |
| `TELEGRAM_BOT_TOKEN` | `tools/telegram_notify.py`, `triggers/telegram_trigger.py` |
| `TELEGRAM_CHAT_ID` | `tools/telegram_notify.py`, `triggers/telegram_trigger.py` |
| `WHATSAPP_API_URL` | `tools/whatsapp_notify.py` |
| `WHATSAPP_TOKEN` | `tools/whatsapp_notify.py` |
| `WHATSAPP_TO` | `tools/whatsapp_notify.py` |
| `TRIGGER_TOKEN` | `triggers/http_trigger.py` |

## Regra

Toda nova integração externa é uma **tool** em `tools/`. Toda nova variável de ambiente deve ser adicionada ao `.env.example`.
