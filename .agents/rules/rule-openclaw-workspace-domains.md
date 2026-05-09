# ---
description: Como dividir skills por workspace/domínio de agente no OpenClaw. Consultar ao criar nova skill ou novo agente.
alwaysApply: model_decision
# ---

# Workspaces por Domínio — OpenClaw

## O problema que isso resolve

Sem divisão, o agente default injeta 20+ skills em todo pedido (~22k tokens).
Com domínios separados, cada agente carrega só o que precisa (~4k tokens).

## Onde fica a configuração

**Um único arquivo:** `entrypoint.sh`
- Função `sync_agent_workspaces()` — define quais skills vão para qual workspace
- Função `filter_default_workspace_skills()` — remove do default o que não é pessoal
- Array `desiredAgents` — define o agente e aponta para o workspace

---

## Os 3 padrões de distribuição de skills

### Padrão A — FULL (todos os agentes generais)
```bash
# entrypoint.sh, linha ~56
local FULL_SKILLS_AGENTS="leads content intel ops researcher ..."
```
Recebem **symlink para `/app/skills` inteiro**. Nova skill aparece automaticamente.
→ Usar para agentes generalistas (ops, researcher, content, intel)

### Padrão B — LISTA EXPLÍCITA (agente com domínio específico)
```bash
# entrypoint.sh, bloco workspace-work (~linha 92)
for skill in github-weekly-summary edital_monitor business-monitor \
             politics_economy_monitor tech-news-digest crm sindico-leads; do
```
Symlinks individuais por skill. Para adicionar: incluir o nome na lista.
→ Usar para agente `work` e qualquer novo agente especializado

### Padrão C — BLOCKLIST (workspace default / pessoal)
```bash
# entrypoint.sh, função filter_default_workspace_skills (~linha 102)
local SKILLS_TO_REMOVE="github-weekly-summary edital_monitor ..."
```
Default recebe tudo e depois remove o que não é pessoal.
→ Para bloquear skill do agente default: adicionar o nome aqui

---

## Domínios atuais

| Workspace | Agente | Skills |
|---|---|---|
| `workspace` (default) | Personal-Assistant | shopping-tracker, vault, weekly-michelin-meal-plan, humanizer, deep-research |
| `workspace-work` | Strategist | github-weekly-summary, edital_monitor, business-monitor, politics_economy_monitor, tech-news-digest, crm, sindico-leads |
| `workspace-content` | Copywriter | todas (FULL) |
| `workspace-ops` | Steward | todas (FULL) |
| `workspace-intel` | Sentinel | todas (FULL) |
| `workspace-leads` | Prospector | nenhuma (skills: []) |
| `workspace-zind-crm-*` | Agentes CRM | só crm/library |

---

## Como criar uma skill nova

**Passo 1** — Criar `skills/<nome-da-skill>/SKILL.md`

**Passo 2** — Decidir o domínio:

```
Skill nova → onde deve aparecer?
├── Todos os agentes gerais?  → não faz nada (FULL_SKILLS pega automático)
├── Agente work (trabalho)?   → adicionar no loop "for skill in..." do workspace-work
│                               E adicionar em SKILLS_TO_REMOVE do filter_default
├── Default (pessoal)?        → não faz nada (default tem o que sobra após o filtro)
└── Novo agente especializado → criar bloco novo igual ao do workspace-work
```

**Passo 3** — Reiniciar o gateway (o `sync_agent_workspaces` roda no boot)

---

## Como criar um novo agente com workspace próprio

1. Criar `agents/<nome>/` com AGENTS.md, SOUL.md, IDENTITY.md, TOOLS.md
2. Adicionar bloco em `sync_agent_workspaces()` com a lista de skills:
```bash
local MEU_DST="$CONFIG_DIR/workspace-<nome>"
local MEU_SRC="$APP_ROOT/agents/<nome>"
if [ -d "$MEU_SRC" ]; then
    mkdir -p "$MEU_DST/skills"
    for f in SOUL.md AGENTS.md IDENTITY.md TOOLS.md; do
        [ -f "$MEU_SRC/$f" ] && cp "$MEU_SRC/$f" "$MEU_DST/$f"
    done
    for skill in skill-a skill-b skill-c; do
        [ -d "$APP_ROOT/skills/$skill" ] && ln -sfn "$APP_ROOT/skills/$skill" "$MEU_DST/skills/$skill"
    done
fi
```
3. Adicionar o agente em `desiredAgents` com `workspace: "~/.openclaw/workspace-<nome>"`
4. Adicionar skills do novo agente em `SKILLS_TO_REMOVE` se não devem aparecer no default

---

## Verificação após restart

```bash
# Skills do default (só pessoais)
docker exec openclaw-gateway ls /root/.openclaw/workspace/skills/

# Skills do workspace específico
docker exec openclaw-gateway ls /root/.openclaw/workspace-work/skills/

# Agente registrado
openclaw agents | grep <nome>
```
