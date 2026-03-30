# OpenClaw — Sub-Agents

> **Resumo:** Sub-agents são execuções de agentes em background, isoladas em sessões próprias, usadas para paralelizar tarefas longas ou pesadas sem bloquear o agente principal.

---

## Comandos principais

- `/subagents list` — lista sub-agentes ativos
- `/subagents kill <id|#|all>` — encerra sub-agente(s)
- `/subagents log <id|#> [limit] [tools]` — exibe logs
- `/subagents info <id|#>` — mostra metadados
- `/subagents send <id|#> <mensagem>` — envia mensagem
- `/subagents steer <id|#> <mensagem>` — direciona
- `/subagents spawn <agentId> <task> [--model <model>] [--thinking <level>]` — cria sub-agente
- `/focus`, `/unfocus`, `/agents`, `/session idle`, `/session max-age` — controle de thread

---

## Funcionamento

- Sub-agentes rodam em sessões isoladas (`agent:<agentId>:subagent:<uuid>`)
- Ao finalizar, anunciam o resultado no canal de origem
- Spawn é não-bloqueante: retorna ID imediatamente
- Entrega resiliente: tenta direto, depois fila, depois backoff
- Cada sub-agente tem contexto e tokens próprios (custo separado)
- Modelos e níveis de "thinking" podem ser customizados por sub-agente

---

## Parâmetros e configuração

```jsonc
{
  "agents": {
    "defaults": {
      "subagents": {
        "maxSpawnDepth": 2, // permite sub-agentes aninhados
        "maxChildrenPerAgent": 5, // filhos ativos por sessão
        "maxConcurrent": 8, // concorrência global
        "runTimeoutSeconds": 900 // timeout padrão
      }
    }
  }
}
```

- `task` (obrigatório)
- `label`, `agentId`, `model`, `thinking`, `runTimeoutSeconds`, `thread`, `mode`, `cleanup`, `sandbox` (opcionais)

---

## Thread-bound sessions

- Sub-agentes podem ser "fixados" em threads (ex: Discord)
- Comandos: `/focus`, `/unfocus`, `/session idle`, `/session max-age`
- Config global: `session.threadBindings.*`

---

## Níveis de profundidade

| Profundidade | Chave de sessão | Papel | Pode spawnar? |
|-------------|-----------------|-------|---------------|
| 0 | agent:<id>:main | Agente principal | Sempre |
| 1 | agent:<id>:subagent:<uuid> | Sub-agente/orquestrador | Se maxSpawnDepth >= 2 |
| 2 | agent:<id>:subagent:<uuid>:subagent:<uuid> | Sub-sub-agente (worker) | Nunca |

- Resultados fluem de baixo para cima (worker → orquestrador → main)
- Limite de filhos ativos por sessão: `maxChildrenPerAgent`
- Parar orquestrador para todos os filhos: `/stop` ou `/subagents kill <id|all>`

---

## Políticas de ferramentas

- Sub-agentes não recebem tools de sessão/sistema por padrão
- Orquestrador (profundidade 1, se maxSpawnDepth >= 2): recebe `sessions_spawn`, `subagents`, `sessions_list`, `sessions_history`
- Workers (profundidade 2): não recebem tools de sessão
- Override via config:

```jsonc
{
  "tools": {
    "subagents": {
      "tools": {
        "deny": ["gateway", "cron"]
        // "allow": ["read", "exec", "process"]
      }
    }
  }
}
```

---

## Limitações e observações

- Anúncio de sub-agente é best-effort (pode perder se gateway reiniciar)
- Compartilham recursos do gateway
- Contexto só injeta AGENTS.md + TOOLS.md
- Profundidade máxima recomendada: 2 (suporta até 5)
- `maxChildrenPerAgent` padrão: 5 (1–20)

---

## Referências
- Veja também: Configuration Reference, Slash commands, ACP Agents.