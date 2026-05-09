# TOOLS.md — Zind Handover

## MCP: mcp-crm (leitura + log)
- `search_contact` — buscar histórico e nome do lead
- `log_conversation_event` — registrar handover, escalação ou opt-out com metadata

## Filesystem: read (apenas skills)
- `read skills/crm/library/human_rules.json`
- `read skills/crm/library/identity_soul.json`

## Negado
- `send_whatsapp_outreach` — responsabilidade do orquestrador
- `sessions_send`, `sessions_spawn` — agent folha, não delega
- `mark_no_interest` — somente o orquestrador via policy block_and_stop
- `write`, `edit`, `exec`, `cron`, `browser`, `web_search`, `web_fetch`, `canvas`
- Qualquer operação de escrita/aprovação no CRM
