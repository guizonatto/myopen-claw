# Módulo 5 — Reporter & Dispatch

Status: `completed`

## Responsabilidade
- Gerar relatório consolidado sem LLM.
- Enviar para Discord a cada hora.

## Interface
- Entrada: agregados do storage.
- Saída: mensagem Discord via gateway REST.

## Checklist
- [x] Criar renderer de relatório para Discord
- [x] Exibir tokens como `exact`, `estimated`, `mixed` ou `n/a`
- [x] Implementar scheduler horário (`HH:05`, `America/Sao_Paulo`)
- [x] Implementar dispatch idempotente
- [x] Adicionar CLI manual para render/inspeção
- [x] Adicionar testes de formatação e janelas

## Evidências
- `llm_usage_telemetry/reporting.py` gera o relatório textual com seções `Ultima hora` e `Acumulado do dia`.
- `llm_usage_telemetry/dispatcher.py` consolida a hora fechada anterior, envia via `/api/message` e evita duplicação por bucket.
- `llm_usage_telemetry/app.py` agenda o dispatch às `HH:05` quando o sidecar sobe.
- `scripts/model_usage_report.py` roda via CLI a partir do root do repo sem depender de LLM.
- Verificado por:
  - `tests/llm_usage/test_dispatch.py`
  - `tests/llm_usage/test_reporting.py`
  - `tests/llm_usage/test_cli.py`
