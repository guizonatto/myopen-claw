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
