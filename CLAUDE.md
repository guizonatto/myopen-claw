# Integração OpenClaw (Node.js) + Python

Este projeto integra o OpenClaw Gateway (Node.js) — um roteador multi-canal para agentes de IA — com agentes Python customizados. O Gateway gerencia canais, sessões e plugins, enquanto este repositório implementa agentes, skills e automações em Python, conectados ao ecossistema OpenClaw.

Referência oficial do Gateway: https://docs.openclaw.ai/

# OpenClaw — Contexto do Projeto

## Identidade e comportamento do agente

@configs/IDENTITY.md
@configs/SOUL.md
@configs/AGENTS.md
@configs/HEARTBEAT.md

## Arquitetura e estrutura de arquivos

@docs/architecture.md

## Regras de atomicidade

@docs/atomic_rules.md

## Decisões registradas

@docs/decisions.md

## Memória

@configs/MEMORY.md

---

## Regras de trabalho

- Antes de criar qualquer arquivo, consulte `docs/architecture.md` para confirmar pasta e nome correto.
- Antes de criar qualquer componente, use o checklist em `docs/atomic_rules.md`.
- Antes de registrar uma decisão importante, adicione em `docs/decisions.md`.
- Antes de alterar identidade ou comportamento do agente, edite os arquivos em `configs/`.
- Use `/new` para scaffoldar qualquer componente novo no lugar correto.
- Nunca duplique regras aqui — edite o doc canônico correspondente.
- Sempre que instalar dependências, plugins ou comandos que precisem rodar no deploy, adicione a entrada correspondente no `entrypoint.sh` para garantir automação total.
- Para versionamento e documentação de cronjobs, siga `.agents/rules/rule-openclaw-cronjob-versioning.md`.

## Regras do projeto

Todas as regras estão em `.agents/rules/`. Consulte antes de implementar qualquer componente relacionado a agentes, MCPs, skills ou crons.

Regras relevantes por tópico:

| Tópico | Arquivo |
|---|---|
| Agente default (Personal-Assistant) — tools, allow, deny | `.agents/rules/rule-openclaw-default-agent-tools.md` |
| Reduzir tokens/schemas de MCP | `.agents/rules/rule-mcp-context-reduction.md` → doc em `docs/mcp-context-reduction.md` |
| Schemas de tools MCP (inputSchema) | `.agents/rules/rule-mcp-tool-schema.md` |
| Criar/deployar um MCP | `.agents/rules/rule-deploy-mcp.md` |
| Agentes OpenClaw (estrutura, identidade) | `.agents/rules/rule-openclaw-agents.md` |
| Cronjobs (criação e versionamento) | `.agents/rules/rule-openclaw-cronjob-versioning.md` |
| Novo skill | `.agents/rules/rule-openclaw-new-skill.md` |
| Hooks OpenClaw | `.agents/rules/rule-openclaw-hooks.md` |
| Workspaces por domínio — onde cada skill vai, como criar agente novo | `.agents/rules/rule-openclaw-workspace-domains.md` |

## graphify

This project has a graphify knowledge graph at graphify-out/.

Rules:
- Before answering architecture or codebase questions, read graphify-out/GRAPH_REPORT.md for god nodes and community structure
- If graphify-out/wiki/index.md exists, navigate it instead of reading raw files
- After modifying code files in this session, run `python3 -c "from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))"` to keep the graph current
