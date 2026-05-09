# TOOLS.md — Zind Cold Contact

## MCP: mcp-crm (leitura)
- `search_contact` — buscar dados do lead (nome, empresa, setor, dor, sinal, histórico)
- `log_conversation_event` — registrar evento outbound após gerar resposta (opcional, feito pelo orquestrador)

## Filesystem: read (apenas skills)
- `read skills/crm/library/stage_playbook.json`
- `read skills/crm/library/identity_soul.json`
- `read skills/crm/library/human_rules.json`

## Negado
- `send_whatsapp_outreach` — responsabilidade do orquestrador
- `sessions_send`, `sessions_spawn` — agent folha, não delega
- `write`, `edit`, `exec`, `cron`, `browser`, `web_search`, `web_fetch`, `canvas`
- Qualquer operação de escrita no CRM (update_contact, mark_no_interest, approve_*)
