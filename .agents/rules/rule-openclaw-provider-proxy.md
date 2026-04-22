# ---
description: Regras para integrar providers de LLM no OpenClaw deste projeto
alwaysApply: model_decision
# ---

# Regras para Provider Proxy — OpenClaw

> Consulte também: [docs/llm-usage-proxy.md](../../docs/llm-usage-proxy.md) e [docs/openclaw-provider-plugins.md](../../docs/openclaw-provider-plugins.md)

## Responsabilidade

- Todo provider de LLM, embedding ou endpoint compatível deve passar pelo `llm-metrics-proxy`.
- O proxy é a fonte de verdade de uso por `service`, `provider` e `model`.
- O gateway não deve falar diretamente com providers externos.

## Regra de Integração

- Modelos usados pelo `openclaw` devem seguir o formato `usage-router/<provider>/<model>`.
- O plugin `usage-router` deve ser o ponto único de entrada do gateway para providers externos.
- `memclaw` e MCPs também devem apontar para o proxy, nunca direto para o provider.

## Obrigatório ao Adicionar um Provider

- configurar o upstream real no proxy
- definir autenticação do provider no container do proxy
- garantir coleta de `success`, `http_status`, `latency_ms`, `error_code` e tokens
- testar pelo menos um caso de sucesso e um de falha
- documentar env vars, limites e formato esperado de payload
- atualizar o `model-stack` para usar o provider via `usage-router`

## Proibido

- plugar provider novo diretamente no `openclaw.json` com base URL externa
- usar exceções fora do proxy para “testes rápidos” e depois manter isso em produção
- introduzir provider novo sem preservar rastreamento por `service/provider/model`

## Critério de Aceite

- o provider aparece no SQLite de telemetria com `provider` e `model` corretos
- o tráfego continua compatível com relatório horário e agregação diária
- a documentação do provider inclui o caminho pelo proxy
