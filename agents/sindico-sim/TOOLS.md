# TOOLS.md - Sindico Sim

## Objetivo
Responder como cliente simulado via JSON estruturado.

## Permitido
- `read` para contexto local minimo, quando necessario.

## Negado
- `sessions_send`, `sessions_spawn`, `sessions_history`.
- `exec`, `cron`, `browser`, `web_search`, `web_fetch`.
- Escrita em MCP CRM.

