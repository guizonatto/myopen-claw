# Módulo 6 — Verification

Status: `completed`

## Checklist
- [x] Validar sucesso com `usage` real
- [x] Validar embedding local com token estimado
- [x] Validar `n/a` quando não houver token confiável
- [x] Validar falhas `429`, `5xx` e timeout
- [x] Validar agregação `exact`, `estimated`, `mixed` e `n/a`
- [x] Validar envio Discord sem agente/LLM
- [x] Validar persistência de `origin_type/origin_name/trigger_type/trigger_name`
- [x] Rodar o rebuild do Graphify

## Evidências
- `python -m unittest tests.llm_usage.test_dispatch tests.llm_usage.test_storage tests.llm_usage.test_reporting tests.llm_usage.test_upstreams tests.llm_usage.test_app tests.llm_usage.test_cli tests.llm_usage.test_service`
  - resultado: `Ran 16 tests ... OK`
- `node --test plugins/usage-router-plugin/tests/model-ref.test.js`
  - resultado: `2 pass, 0 fail`
- `node --check plugins/usage-router-plugin/index.js`
  - resultado: exit `0`
- `docker compose config > $null`
  - resultado: exit `0`
- `python scripts/model_usage_report.py`
  - resultado: relatório manual renderizado com `Ultima hora` e `Acumulado do dia`
- `node scripts/apply-model-stack.mjs --config <temp> --stack configs/model-stack.json --print`
  - resultado: `primary = usage-router/groq/allam-2-7b`
- `python -c "from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))"`
  - primeira tentativa falhou por encoding `charmap` do terminal Windows
- `PYTHONUTF8=1` + `PYTHONIOENCODING=utf-8` + rebuild do Graphify
  - resultado: `Rebuilt: 711 nodes, 895 edges, 63 communities`
- `python -m unittest tests.llm_usage.test_app tests.llm_usage.test_storage tests.llm_usage.test_service tests.llm_usage.test_upstreams`
  - resultado: `Ran 20 tests ... OK`
- `docker exec llm-metrics-proxy python -c "<request + sqlite check>"`
  - resultado: último evento persistido com `origin_type=skill`, `origin_name=daily-content-creator`, `trigger_type=cron`, `trigger_name=Daily Content Creator — IA`
- `docker exec llm-metrics-proxy python -c "<direct discord api test>"`
  - resultado: Discord respondeu `200` ao envio direto para `MODEL_USAGE_REPORT_DISCORD_CHANNEL_ID`
- `docker exec llm-metrics-proxy python -c "import asyncio; ... dispatch_hourly_report(load_settings())"`
  - resultado: `True` após corrigir auth, troca da superfície de envio e chunking do relatório acima de `2000` caracteres
- `MODEL_USAGE_ESTIMATE_CHAT_TOKENS=true` + `python -m unittest tests.llm_usage.test_service tests.llm_usage.test_dispatch tests.llm_usage.test_reporting`
  - resultado: `Ran 20 tests ... OK`, incluindo cobertura para `chat` sem `usage` virar `estimated` quando a flag estiver ligada
- `docker exec llm-metrics-proxy python -c "<short mistral request + sqlite check>"`
  - resultado: novo evento real em `mistral/mistral-large-latest` com `token_accuracy=exact`, `total_tokens=15`; o pipeline continua preferindo `exact` e só usa `estimated` como fallback
- `MODEL_USAGE_CAPTURE_PAYLOADS=full` + `python -m unittest tests.llm_usage.test_service tests.llm_usage.test_dispatch tests.llm_usage.test_storage tests.llm_usage.test_reporting`
  - resultado: `Ran 25 tests ... OK`, incluindo cobertura para payload completo e métricas `chars/words/estimated_tokens`
- `docker exec llm-metrics-proxy python -c "<full capture request + sqlite check>"`
  - resultado: último evento real persistiu `request_payload`, `response_payload`, `input_chars/input_words/input_estimated_tokens` e `response_chars/response_words/response_estimated_tokens`
- `PYTHONUTF8=1` + `PYTHONIOENCODING=utf-8` + `python -c "from graphify.watch import _rebuild_code; ..."`
  - resultado: falhou novamente por lock em `graphify-out/cache/*.tmp` (`WinError 5`); código e testes ficaram atualizados, mas o rebuild automático não concluiu neste host
