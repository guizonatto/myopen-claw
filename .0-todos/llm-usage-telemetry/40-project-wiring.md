# Módulo 4 — Project Wiring

Status: `completed`

## Responsabilidade
- Ligar gateway, memclaw, MCPs e sidecar ao proxy.
- Fazer isso só por env/config/bootstrap do projeto.

## Checklist
- [x] Adicionar sidecar `llm-metrics-proxy` no `docker-compose.yml`
- [x] Adicionar envs novas ao projeto
- [x] Reapontar `memclaw.llmApiBaseUrl`
- [x] Reapontar `memclaw.embeddingApiBaseUrl`
- [x] Preparar `memories_mcp.OLLAMA_URL` para uso via proxy
- [x] Reescrever model stack para `usage-router/...`
- [x] Prefixar skill pins para `usage-router/...`
- [x] Registrar o mapa final de quem fala com quem

## Evidências
- `docker-compose.yml` ganhou o sidecar `llm-metrics-proxy`, volume persistente e rewiring de `openclaw-gateway` e `cortex-mem`.
- `.env.example` documenta `MODEL_USAGE_PROXY_*`, timezone e canal Discord do relatório.
- `entrypoint.sh` reconcilia a config do gateway, ativa `usage-router`, ajusta o plugin `memclaw` e instala o provider local.
- `scripts/apply-model-stack.mjs` prefixa automaticamente os modelos com `usage-router/` e registra o provider no config final.
- `configs/model-stack.json` e skill pins foram migrados para refs `usage-router/...`.
- `mcps/memories_mcp/memories.py` ficou apto a usar `OLLAMA_URL`; o path esperado para observabilidade é `/memories_mcp/api/embeddings` quando esse MCP for instanciado na stack.
