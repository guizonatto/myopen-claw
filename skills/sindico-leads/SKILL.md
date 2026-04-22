---
name: sindico-leads
description: "Buscar e enriquecer leads de síndicos profissionais e registrar no CRM (cheap-first)."
metadata:
  openclaw:
    model: usage-router/mistral/mistral-medium-2508
---


# SKILL: sindico-leads

## Objetivo
Encontrar síndicos profissionais em fontes públicas na web, enriquecer com dados úteis e cadastrar/atualizar no CRM como `lead`, evitando duplicatas.

## Estratégia (cheap-first)
1. Chame a tool MCP `execute_lead_skill` do servidor `mcp-leads` com `operation="sindico_leads"`.
2. Só faça `web_search`/`web_fetch` manual se o MCP estiver indisponível.
3. `browser` só quando necessário (JS-heavy/login).

## Mapeamento (CRM)
- Identifique com alta confiança (nome + pelo menos 1 entre e-mail/telefone/username).
- Cadastre novos leads; atualize campos novos em leads existentes.
- Se houver divergência relevante (telefone/e-mail/empresa), registre como acontecimento/nota no CRM.

## Memória
- Se descobrir fontes que funcionam bem, registre uma memória curta no MemClaw com as fontes e taxa de sucesso.

# User response
- Responda apenas com contagens: novos, atualizados, divergências.
- Não inclua PII (telefones/e-mails) nem lista de leads.
- Se não encontrar leads: `Leads: 0 novos, 0 atualizados, 0 divergências`.

## Referências
- `skills/crm`
