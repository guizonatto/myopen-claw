# LLM Usage Telemetry

Status geral: `completed`

## Objetivo
- Medir uso de `service/provider/model` no `openclaw`, `memclaw` e chamadas diretas de embedding dos MCPs.
- Registrar `attempts`, `failures`, latência, RPM e tokens com qualidade explícita.
- Enviar relatório horário para Discord sem usar LLM.

## Ordem de execução
- [x] Criar a estrutura de tracking em `.0-todos/llm-usage-telemetry/`
- [x] Implementar provider plugin `usage-router`
- [x] Implementar proxy HTTP + passthrough + storage
- [x] Ligar compose/bootstrap/configs ao proxy
- [x] Implementar reporter/dispatch horário
- [x] Verificar fim a fim e rebuild do Graphify

## Decisões travadas
- Não mexer no core do OpenClaw.
- Discord é o destino padrão do relatório.
- Janela padrão: `última hora fechada + acumulado do dia`.
- Tokens devem ser reportados como `exact`, `estimated`, `mixed` ou `n/a`.
- `attempts`, `failures`, `rpm_avg` e `rpm_peak` são métricas exatas.
- Proveniência de execução deve ser persistida no proxy como `origin_*` e `trigger_*`, com prioridade para `skill` inferida e `cron` explícito.

## Matriz de interfaces
| Módulo | Entrada | Saída | Consumidor |
|---|---|---|---|
| Provider plugin | model refs do gateway (`usage-router/<provider>/<model>`) | chamadas OpenAI-compatible para `MODEL_USAGE_PROXY_URL=/openclaw/v1` com `payload.model` preservado | Metrics proxy |
| Metrics proxy | HTTP `/v1/*`, `/api/embeddings`, `/{service}/v1/*`, `/{service}/api/embeddings` | passthrough para upstream + evento bruto persistido | Storage |
| Storage/agregação | eventos brutos com `token_accuracy=exact|estimated|unavailable` | agregados `last-hour` e `day-to-date` com `token_quality=exact|estimated|mixed|n/a` | Reporter |
| Project wiring | envs, compose, bootstrap, model stack, skill pins | tráfego reapontado para o proxy | Todos |
| Reporter/dispatch | agregados do storage | mensagem Discord via Discord Bot API (gateway fallback legado) | Operação |

## Blockers
- Nenhum no momento.

## Mapa final
- `openclaw-gateway` usa o plugin `usage-router`, que aponta para `MODEL_USAGE_PROXY_URL` com base default `http://llm-metrics-proxy:8080/openclaw/v1`.
- `cortex-mem` e o plugin `memclaw` usam `http://llm-metrics-proxy:8080/memclaw/v1` para texto e embeddings.
- O proxy suporta um namespace adicional `/{service}` para qualquer MCP futuro; para `memories_mcp`, o path esperado é `http://llm-metrics-proxy:8080/memories_mcp/api/embeddings`.
- `provider/model` reais continuam no `payload.model` como `usage-router/<provider>/<model>` e são resolvidos no proxy para o upstream final.

## Evidências recentes
- Proxy Python implementado em `llm_usage_telemetry/` com app FastAPI, storage SQLite, agregação, scheduler e dispatch.
- Plugin local criado em `plugins/usage-router-plugin/` e instalado automaticamente via `entrypoint.sh`.
- Rewiring aplicado em `docker-compose.yml`, `.env.example`, `scripts/apply-model-stack.mjs` e skill/model pins.
- Verificação concluída com `16` testes Python verdes, `2` testes Node verdes, `docker compose config` válido e Graphify rebuild concluído.
- Proveniência fim a fim validada no SQLite com um evento gravado como `origin_type=skill`, `origin_name=daily-content-creator`, `trigger_type=cron`, `trigger_name=Daily Content Creator — IA`.
- Dispatch horário corrigido para enviar direto ao Discord com chunking (`<=1900` chars por mensagem) e fallback para superfícies legadas do gateway.
- Validação manual no container: `dispatch_hourly_report(load_settings())` retornou `True` após rebuild do `llm-metrics-proxy`.
