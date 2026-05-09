# ---
description: Antes de expor ferramentas MCP a agentes, usar crm-proxy pattern para minimizar schema injection. Ver doc canônico em docs/mcp-context-reduction.md
alwaysApply: false
# ---

# Redução de Contexto via MCP Proxy

Ao criar ou modificar um MCP que será usado por agentes OpenClaw:
**não exponha todas as tools diretamente** — use o padrão proxy descrito em `docs/mcp-context-reduction.md`.

## Regra rápida

- MCP com ≥ 5 tools → criar `proxy.py` no mesmo diretório que expõe 1 tool genérica `crm(action, params)`
- Documentar as actions disponíveis no `AGENTS.md` de cada agente especializado
- Schemas com `anyOf`/`oneOf`/`allOf` no top level → mover regra para `description` da tool

## Quando aplicar

- Ao criar um novo MCP com múltiplas tools
- Ao notar `bundle-tools > 10s` nos logs do gateway
- Ao ver modelos falhando com `Request too large` ou `413`
- Ao adicionar um MCP a um agente que já tem contexto acima de 10k chars

## Referência completa

`docs/mcp-context-reduction.md`
