# ---
description: Regras para heartbeat — OpenClaw
alwaysApply: model_decision
# ---
# Regras para Heartbeat — OpenClaw

> Consulte também: [configs/HEARTBEAT.md](../../configs/HEARTBEAT.md)

## Responsabilidade
- O heartbeat monitora a saúde do agente e registra batidas periódicas.
- Pode acionar alertas em caso de falha ou ausência de batidas.

## Estrutura
- Implementado em `configs/HEARTBEAT.md` e scripts dedicados.
- Deve ser configurável (intervalo, destino de alerta).

## Boas práticas
- Heartbeat deve ser leve, resiliente e não bloquear o agente.
