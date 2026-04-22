# ---
description: Regras para standing orders — OpenClaw
alwaysApply: model_decision
# ---
# Regras para Standing Orders — OpenClaw

> Consulte também: [docs/standing-orders-openclaw.md](../../docs/standing-orders-openclaw.md)

## Conceito
- Standing orders concedem autoridade permanente ao agente para executar programas definidos, sem necessidade de instrução manual recorrente.

## Estrutura
- Devem ser declaradas em `configs/AGENTS.md` (ou arquivo referenciado).
- Cada ordem define: escopo, triggers, gates de aprovação e regras de escalonamento.
- O agente executa ordens automaticamente, só pedindo aprovação em exceções.

## Boas práticas
- Use triggers claros (cron, evento, condição).
- Defina limites e critérios de escalonamento.
- Documente cada ordem com autoridade, trigger, aprovação e escalonamento.
