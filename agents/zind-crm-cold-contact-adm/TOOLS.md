# TOOLS.md — Zind Cold Contact ADM

## MCP: mcp-crm (leitura + log)
- `search_contact` — buscar dados da administradora (nome, contato, histórico)
- `log_conversation_event` — registrar eventos outbound
- `update_contact` — atualizar stage e nota após interação

## Filesystem: read (apenas skills)
- `read skills/crm/library/battlecards_adm.json`
- `read skills/crm/library/human_rules.json`
- `read skills/crm/library/identity_soul.json`

## Negado
- `send_whatsapp_outreach` — responsabilidade do orquestrador
- `sessions_send`, `sessions_spawn` — agent folha, não delega
- `add_contact`, `mark_no_interest`, `approve_*` — requerem permissão específica
- `write`, `edit`, `exec`, `cron`, `browser`, `web_search`, `web_fetch`, `canvas`
