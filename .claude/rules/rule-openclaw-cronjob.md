# ---
description: Regras para cronjobs — OpenClaw
alwaysApply: model_decision
# ---
# Regras para Cronjobs — OpenClaw

> Consulte também: [docs/architecture.md](../../docs/architecture.md)

## Responsabilidade
- Crons apenas agendam a execução de pipes em horários fixos (usando APScheduler).
- Nunca implementam lógica de negócio ou transformação de dados.

## Estrutura
- Cada cronjob reside em `crons/`.
- Deve importar e acionar pipes via `run()`.
- Parâmetros de agendamento devem ser configuráveis.

## Atomicidade
- Cada cronjob deve ser testável isoladamente, simulando o agendamento.
