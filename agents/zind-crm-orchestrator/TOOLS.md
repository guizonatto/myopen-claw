# TOOLS.md — Zind CRM Orchestrator

## MCP disponível: mcp-crm

Operações permitidas:

| Tool | Uso no pipeline |
|---|---|
| `search_contact` | Passo 1: resolver telefone → lead_id. Passo 5: buscar contexto completo. |
| `buffer_incoming_messages` | Passo 2: agregar burst de mensagens. |
| `route_conversation_turn` | Passo 3: classificar intent e escolher specialist. |
| `log_conversation_event` | Passo 6: registrar inbound. |
| `send_whatsapp_outreach` | Passo 8: enviar resposta gerada pelo specialist. |
| `mark_no_interest` | Passo 4 (policy block_and_stop): registrar desinteresse. |
| `process_inbound_message` | Fallback automatizado apenas — não usar no fluxo normal. |

Operações **não** disponíveis neste agent:
- `approve_first_touch`, `approve_strategy_updates` — requerem role sales_manager
- `start_feedback_review_session`, `generate_strategy_update_proposal` — responsabilidade do zind-crm-reviewer
- `evaluate_dormant_leads`, `send_daily_improvement_report` — workers separados

## Sessions (delegação)

| Tool | Uso |
|---|---|
| `sessions_send` | Delegar para sub-agent e aguardar resposta (Passo 7). |
| `sessions_list` | Consultar sessões ativas se necessário. |

Negado: `sessions_spawn` (não criar sessões em background neste flow).

## Filesystem
- `read` permitido apenas para skills: `read skills/crm/SKILL.md`
- `write`, `edit` negados
- `exec`, `cron`, `browser`, `web_search`, `web_fetch`, `canvas` negados
