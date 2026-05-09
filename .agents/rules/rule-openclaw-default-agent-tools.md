# ---
description: Configuração canônica de ferramentas do agente default (Personal-Assistant). Consultar antes de modificar tools, allow, deny ou subagents do agente default.
alwaysApply: false
# ---

# Agente Default — Configuração de Ferramentas

## Configuração canônica (entrypoint.sh `desiredAgents`)

```js
{
  id: "default",
  default: true,
  workspace: "~/.openclaw/workspace",
  tools: {
    allow: ["sessions_send", "sessions_list", "read", "web_search", "web_fetch", "browser"],
    deny:  ["mcp-crm", "crm-proxy", "mcp-shopping", "mcp-leads", "mcp-trends", "obsidian",
            "write", "edit", "exec", "canvas", "sessions_spawn"],
  },
  subagents: { allowAgents: ["librarian", "researcher", "zind-crm-orchestrator", "ops"] },
}
```

## Por que esta configuração

**`allow` não-vazio é obrigatório para reduzir schemas.**
Quando `allow` está vazio ou ausente, o OpenClaw injeta os schemas de TODOS os MCPs no system prompt (~40k chars). Com `allow` explícito, só os schemas das tools listadas são injetados.

**`exec` está proibido intencionalmente.**
Com `exec` habilitado o agente tentou: rodar `mcp` como comando shell, executar scripts Python direto, chamar APIs via curl. Causa caos. Se precisar de operações de sistema, delegar para `ops`.

**MCPs no deny reduzem o contexto.**
O agente default é um roteador — não precisa de acesso direto ao CRM, leads ou trends. Cada MCP no deny é um schema que não é injetado (redução de ~3-14k chars por MCP removido).

**`skills: []` mantém contexto leve.**
Sem lista de skills injetada (~8k chars). O agente usa o que precisa via `read` ou delegando para especialistas.

## O que o agente default pode fazer

| Capacidade | Como |
|---|---|
| Responder perguntas, pesquisar | `web_search`, `web_fetch`, `browser` |
| Listar crons e status | `read /root/.openclaw/cron/jobs.json` e `jobs-state.json` |
| Rodar um cron manualmente | Delegar para `ops` via `sessions_send` |
| Operações CRM / WhatsApp / vendas | Delegar para `zind-crm-orchestrator` |
| Pesquisa web aprofundada | Delegar para `researcher` |
| Vault, notas, Obsidian | Delegar para `librarian` |
| Operações de sistema / exec | Delegar para `ops` |

## O que NÃO fazer

- **Não adicionar `exec`** ao allow do default — causa tentativas de rodar comandos aleatórios
- **Não deixar `allow` vazio** — injeta todos os schemas de todos os MCPs (~40k chars)
- **Não adicionar MCPs ao allow** — delegar para sub-agentes especializados em vez disso
- **Não remover `web_search`/`web_fetch`** — sem eles o agente não consegue responder perguntas básicas
- **Não adicionar `cron`** — essa tool não existe no runtime embedded (gera warning e confunde o modelo)

## Sintoma de configuração errada

| Sintoma | Causa provável |
|---|---|
| Agent diz "MCP não disponível, forneça endpoint" | `allow` vazio ou MCP ausente do allow do sub-agente correto |
| Agent roda `mcp`, `python3` ou `curl` direto | `exec` habilitado no default |
| `bundle-tools > 30s` | `allow` vazio (todos MCPs sendo inicializados) |
| Agent diz "não tenho acesso ao sistema" | `read` ausente do allow |
| Agent sugere `openclaw doctor --fix` | Model confuso, `exec` habilitado ou allow muito restrito |

## Onde fica a configuração

A fonte canônica é o `entrypoint.sh`, seção `desiredAgents`, entrada `id: "default"`.
O `entrypoint.sh` reconcilia esta config no startup do gateway — mudanças só têm efeito após restart.
