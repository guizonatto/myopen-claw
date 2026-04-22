# Módulo 3 — Storage & Aggregation

Status: `completed`

## Responsabilidade
- Persistir eventos brutos em SQLite.
- Agregar métricas por `service/provider/model/request_kind`.
- Controlar idempotência de envio de relatórios.

## Interface
- Entrada: eventos do proxy.
- Saída: agregados `last-hour` e `day-to-date`.

## Esquema mínimo
- `usage_events`
- `report_dispatches`

## Checklist
- [x] Criar esquema SQLite
- [x] Persistir `token_accuracy = exact | estimated | unavailable`
- [x] Agregar `attempts/successes/failures`
- [x] Agregar `rpm_avg/rpm_peak`
- [x] Agregar tokens exatos e estimados separadamente
- [x] Implementar deduplicação de dispatch
- [x] Adicionar testes de agregação e qualidade de tokens

## Evidências
- `llm_usage_telemetry/storage.py` cria `usage_events` e `report_dispatches`.
- O consolidado agora distingue `exact`, `estimated`, `mixed` e `n/a`.
- `llm_usage_telemetry/reporting.py` renderiza tokens com rótulo explícito em vez de colapsar estimativas puras como `mixed`.
- A stack passou a suportar `MODEL_USAGE_ESTIMATE_CHAT_TOKENS=true` para estimar `chat/responses` bem-sucedidos sem `usage` explícito do provider.
- A stack passou a suportar `MODEL_USAGE_CAPTURE_PAYLOADS=full`, persistindo payload completo de request/response e métricas `chars/words/estimated_tokens` para auditoria.
- Verificado por:
  - `tests/llm_usage/test_storage.py`
  - `tests/llm_usage/test_reporting.py`
  - `tests/llm_usage/test_dispatch.py`
