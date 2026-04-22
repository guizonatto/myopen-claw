---
name: sindico-leads
description: "Busca leads por fonte, aprende taxa de WhatsApp por fonte e registra no CRM."
metadata:
  openclaw:
    model: usage-router/mistral/mistral-medium-2508
---

# SKILL: leads/fetch

## Objetivo
Buscar leads empresariais por fonte, normalizar o output e retornar lista pronta para o CRM.
Cada fonte tem sua config em `skills/leads/<fonte>.yaml`.

## Fontes disponíveis

| Fonte | Config | Estratégia |
|---|---|---|
| `sindico_leads` | `sindico_leads.yaml` | MCP `mcp-leads` → fallback web_search |
| `google_maps` | — | Google Places API (`GOOGLE_MAPS_API_KEY`) |
| `instagram_biz` | — | Instagram scraping (`INSTAGRAM_SESSION`) |
| `linkedin_biz` | — | LinkedIn scraping (`LINKEDIN_SESSION`) |

## Estratégia cheap-first (sindico_leads)
1. Chamar MCP `mcp-leads` com `operation="sindico_leads"` — mais barato e rápido.
2. Se MCP indisponível: `web_search` direto com query do `sindico_leads.yaml`.
3. `browser` apenas quando necessário (sites JS-heavy ou com login).

## Output normalizado
Todos os campos abaixo são retornados por qualquer fonte:
```
nome | telefone | whatsapp | email | cidade | cnae | origem
```
Campos extras (sindico_leads): `apelido`, `tipo`, `linkedin`, `instagram`, `empresa`, `cargo`, `setor`, `notas`

## Mapeamento CRM
- Identificar por: nome + pelo menos 1 entre email/telefone.
- Lead novo → `add_contact`.
- Lead existente com campo novo → `update_contact`.
- Divergência relevante (telefone/email diferente) → registrar como nota no CRM.

## Memória
- O agente que chama esta skill registra deterministicamente: `fonte`, `total`, `com_whatsapp`, `duplicatas`, `taxa_wpp`.
- Não cabe à skill registrar memória — isso é responsabilidade do agente (`LeadFetcherAgent`).

## Resposta ao usuário
Apenas contagens: `X novos, Y atualizados, Z divergências`.
Não incluir PII (telefones, e-mails) na resposta.

## Referências
- `skills/crm` — operações CRM
- `agents/lead_fetcher/` — agente que usa esta skill e mantém o ranking de fontes
