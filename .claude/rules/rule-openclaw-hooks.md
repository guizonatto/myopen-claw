# ---
description: Regras para hooks — OpenClaw
alwaysApply: model_decision
# ---
# Regras para Hooks — OpenClaw

> Consulte também: [docs/hooks-openclaw.md](../../docs/hooks-openclaw.md)

## Responsabilidade
- Hooks automatizam ações em resposta a eventos do agente (ex: /new, /reset, /stop).
- Podem ser scripts locais ou webhooks externos.

## Estrutura
- Hooks residem em `.claude/hooks/` (diretório padrão do projeto OpenClaw) ou podem ser empacotados em plugins.
- Sempre que criar ou alterar hooks, garanta que o diretório `.claude/hooks/` está incluído no `Dockerfile` para deploy correto no ambiente de produção.
- Devem ser pequenos, auditáveis e ativados explicitamente via CLI ou config.

## Boas práticas
- Use hooks para snapshot de memória, auditoria de comandos e automações de ciclo de vida.
- Hooks devem ser confiáveis, rápidos e não bloquear o fluxo principal do agente.
