---
name: openclaw-specialist
description: Especialista completo em OpenClaw — arquitetura, canais, ferramentas, automação, segurança, nodes, configuração e exemplos.
user-invocable: true
---

## Referência da documentação OpenClaw

Toda a documentação oficial está em `docs/openclaw_reference.md`.
Leia esse arquivo sempre que precisar responder perguntas sobre OpenClaw.

**Para atualizar a documentação:** fazer novo crawl de https://docs.openclaw.ai/ e sobrescrever `docs/openclaw_reference.md`.

---

## Regras sempre ativas para criação de arquivos neste projeto

Antes de criar qualquer arquivo `.py`, verificar:

### Onde cada tipo vai
- Coleta ou transformação de dados → `skills/`
- Integração externa (envio de mensagem, scraping, API de terceiro) → `tools/`
- Orquestração de skills + tools → `pipes/`
- Agendamento por horário (APScheduler) → `crons/`
- Ativação por evento externo (webhook, bot, mensagem) → `triggers/`
- Lógica condicional entre pipes → `agents/`
- Utilitário interno reutilizável em múltiplos módulos → `openclaw/`

### Naming obrigatório
- `skills/`: `{dominio}_{acao}.py` → ex: `linkedin_fetch.py`
- `tools/`: `{canal}_notify.py` / `{canal}_scraper.py` → ex: `telegram_notify.py`
- `pipes/`: `{processo}_pipe.py` → ex: `linkedin_monitor_pipe.py`
- `crons/`: `{processo}_cron.py` → ex: `linkedin_monitor_cron.py`
- `triggers/`: `{canal}_trigger.py` → ex: `http_trigger.py`
- `agents/`: `{nome}_agent.py` → ex: `trends_agent.py`

### Proibido
- Criar arquivos `.py` de lógica de negócio diretamente em `openclaw/`
- Criar código de notificação fora de `tools/`
- Colocar lógica de orquestração dentro de `crons/` ou `triggers/`
- Hardcodar credenciais, tokens ou IDs — sempre via `os.environ.get()`
- Criar nova variável de ambiente sem adicionar ao `.env.example`
