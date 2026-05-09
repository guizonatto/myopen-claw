# TOOLS.md — Zind Qualifier

## MCP: mcp-crm (leitura + criação de indicações)
- `search_contact` — buscar dados completos do lead, histórico de interações
- `log_conversation_event` — registrar evento outbound (opcional, feito pelo orquestrador)
- `add_contact` — **somente** para registrar novo contato recebido via indicação de gatekeeper (Etapa 1D)

## Filesystem: read (apenas skills)
- `read skills/crm/library/stage_playbook.json`
- `read skills/crm/library/battlecards.json`
- `read skills/crm/library/human_rules.json`
- `read skills/crm/library/identity_soul.json`

## Negado
- `send_whatsapp_outreach` — responsabilidade do orquestrador
- `sessions_send`, `sessions_spawn` — agent folha, não delega
- `write`, `edit`, `exec`, `cron`, `browser`, `web_search`, `web_fetch`, `canvas`
- `approve_strategy_updates`, `approve_first_touch`, `mark_no_interest` — requerem permissão específica

