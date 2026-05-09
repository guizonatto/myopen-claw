# TOOLS.md — Zind Reviewer

## MCP: mcp-crm (leitura + revisão)
- `start_feedback_review_session` — abrir sessão de revisão de batch
- `record_human_feedback` — registrar feedback coletado do revisor
- `generate_strategy_update_proposal` — gerar proposta para aprovação
- `list_contacts_to_follow_up` — analisar estado atual do pipeline
- `search_contact` — amostrar interações específicas para análise

## Filesystem: read (apenas skills)
- `read skills/crm/library/message_strategy_seed.json`
- `read skills/crm/library/stage_playbook.json`
- `read skills/crm/library/battlecards.json`

## Negado
- `approve_strategy_updates` — requer role sales_manager
- `send_whatsapp_outreach` — nunca envia para leads
- `sessions_send`, `sessions_spawn` — não delega para outros agents
- `write`, `edit`, `exec`, `cron`, `browser`, `web_search`, `web_fetch`, `canvas`
- `mark_no_interest`, `approve_first_touch` — operações críticas fora do escopo
