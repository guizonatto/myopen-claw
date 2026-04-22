# Módulo 2 — Metrics Proxy

Status: `completed`

## Responsabilidade
- Receber tráfego OpenAI-compatible e Ollama-compatible.
- Encaminhar ao upstream real.
- Registrar cada tentativa com sucesso/falha/latência/tokens.

## Interface
- Entrada:
  - `/v1/chat/completions`
  - `/v1/responses`
  - `/v1/embeddings`
  - `/api/embeddings`
  - `/{service_name}/v1/chat/completions`
  - `/{service_name}/v1/responses`
  - `/{service_name}/v1/embeddings`
  - `/{service_name}/api/embeddings`
  - `/healthz`
- Saída:
  - resposta passthrough
  - evento bruto persistido

## Checklist
- [x] Criar app HTTP do proxy
- [x] Implementar roteamento por provider/model
- [x] Implementar passthrough OpenAI-compatible
- [x] Implementar passthrough Ollama embeddings
- [x] Persistir evento bruto no storage
- [x] Definir política de erro observada

## Evidências
- `llm_usage_telemetry/app.py` expõe healthcheck, rotas OpenAI-compatible, rotas Ollama-compatible e service-scoped routes.
- `llm_usage_telemetry/service.py` resolve `provider/model`, repassa o request e grava evento bruto no SQLite.
- Erros `429`, `5xx` e timeout são registrados como falhas; embeddings sem `usage` recebem estimativa determinística.
- Verificado por `tests/llm_usage/test_service.py` e `tests/llm_usage/test_app.py`.
