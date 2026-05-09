# TOOLS.md — Zind Closer

## MCP: mcp-crm (leitura + log)
- `search_contact` — buscar dados do lead, histórico, best_contact_window, stage
- `log_conversation_event` — registrar handover ou escalaç��o com metadata apropriado

## Filesystem: read (apenas skills)
- `read skills/crm/library/stage_playbook.json`
- `read skills/crm/library/human_rules.json`
- `read skills/crm/library/identity_soul.json`

## Negado
- `send_whatsapp_outreach` — responsabilidade do orquestrador
- `sessions_send`, `sessions_spawn` — agent folha, não delega
- `write`, `edit`, `exec`, `cron`, `browser`, `web_search`, `web_fetch`, `canvas`
- `approve_first_touch`, `approve_strategy_updates` — requerem role sales_manager
- `mark_no_interest` — somente o orquestrador pode acionar via policy block_and_stop
