# Proxy de Uso de LLM

Este projeto usa um proxy local de telemetria para centralizar chamadas de modelos, preservar a observabilidade por provider/model e manter o relatório de uso independente de LLM.

## Objetivo

O `llm-metrics-proxy` é a camada obrigatória entre os serviços do stack e os providers de LLM.

Ele existe para:

- registrar uso por `service`, `provider`, `model` e `request_kind`
- medir `attempts`, `failures`, `latency_ms` e `http_status`
- capturar `input_tokens`, `output_tokens` e `total_tokens`
- marcar qualidade dos tokens como `exact`, `estimated` ou `unavailable`
- consolidar relatórios horários e acumulados do dia sem chamar outro modelo

Sem esse proxy, o projeto perde rastreabilidade por provider/model e fica dependente de logs fragmentados ou comportamento específico de cada provider.

## Arquitetura

Fluxo principal:

1. `openclaw` seleciona um modelo no formato `usage-router/<provider>/<model>`.
2. O plugin local `usage-router` resolve esse model ref e encaminha a chamada para o proxy.
3. O proxy escolhe o upstream correto para o provider real e faz o passthrough da requisição.
4. Antes de responder ao chamador, o proxy grava um evento bruto em SQLite.
5. O reporter lê esse SQLite e envia relatórios horários para o canal configurado.

Fluxos cobertos hoje:

- `openclaw -> usage-router plugin -> llm-metrics-proxy -> provider`
- `memclaw -> llm-metrics-proxy -> provider`
- MCPs e outros serviços podem entrar pelo mesmo proxy usando um path próprio de `service`

## Fonte de Verdade

O banco de telemetria fica em `MODEL_USAGE_DB_PATH`.

Tabela principal:

- `usage_events`: eventos brutos por tentativa de request

Tabela de controle:

- `report_dispatches`: janelas de relatório já enviadas, para evitar duplicação

Campos relevantes de `usage_events`:

- `timestamp`
- `service`
- `provider`
- `model`
- `request_kind`
- `success`
- `http_status`
- `latency_ms`
- `input_tokens`
- `output_tokens`
- `total_tokens`
- `token_accuracy`
- `error_code`
- `error_message`

Essa base é a fonte de verdade para qualquer análise operacional sobre uso de modelos neste projeto.

## Serviços e Paths

Os services são discriminados pelo path usado no proxy.

Exemplos:

- `openclaw`: `http://llm-metrics-proxy:8787/openclaw/v1/...`
- `memclaw`: `http://llm-metrics-proxy:8787/memclaw/v1/...`
- outros serviços podem seguir o mesmo padrão com `/{service}/v1/...`

Para embeddings compatíveis com Ollama, o proxy também aceita:

- `/{service}/api/embeddings`

## Regras de Integração de Provider

Todo provider novo deve ser integrado por meio deste proxy.

Obrigatório:

- expor o provider ao gateway pelo formato `usage-router/<provider>/<model>`
- configurar o upstream real no proxy
- garantir que o `service` fique explícito no path ou nos headers internos
- manter a coleta de tokens, erros e latência nessa camada

Proibido:

- apontar `openclaw`, `memclaw` ou MCPs diretamente para o endpoint externo do provider
- criar exceções que escapem do SQLite de telemetria
- adicionar provider novo apenas no `model-stack` sem passar pelo proxy

## Variáveis de Ambiente

Variáveis principais:

- `MODEL_USAGE_PROXY_ENABLED`
- `MODEL_USAGE_PROXY_URL`
- `MODEL_USAGE_DB_PATH`
- `MODEL_USAGE_REPORT_TIMEZONE`
- `MODEL_USAGE_REPORT_DISCORD_CHANNEL_ID`
- `MODEL_USAGE_RETENTION_DAYS`

Providers usam suas credenciais próprias no container do proxy, por exemplo:

- `GROQ_API_KEY`
- `MISTRAL_API_KEY`
- `CEREBRAS_API_KEY`
- `OPENROUTER_API_KEY`
- `GEMINI_API_KEY`

## Google / Gemini

O provider `google` tem dois modos suportados na configuração do proxy:

- `GOOGLE_AUTH_MODE=gemini_api`
- `GOOGLE_AUTH_MODE=vertex_oauth`

Para o caminho grátis com rate limits do Google AI Studio, o modo esperado é:

- `GOOGLE_AUTH_MODE=gemini_api`
- `GEMINI_API_KEY=<sua-chave>`

Se o provider voltar a ser habilitado no stack, isso deve acontecer pelo proxy, nunca com acesso direto do gateway ao endpoint do Google.

## Checklist para Novo Provider

- adicionar ou ajustar o upstream no proxy
- validar autenticação e payload do provider real
- expor o model ref via `usage-router/<provider>/<model>`
- atualizar `configs/model-stack.json` para usar o novo provider pelo `usage-router`
- testar sucesso, falha e captura de `usage`
- documentar variáveis e limitações do provider

## Arquivos Relacionados

- [plugins/usage-router-plugin/index.js](../plugins/usage-router-plugin/index.js)
- [llm_usage_telemetry/service.py](../llm_usage_telemetry/service.py)
- [llm_usage_telemetry/storage.py](../llm_usage_telemetry/storage.py)
- [llm_usage_telemetry/dispatcher.py](../llm_usage_telemetry/dispatcher.py)
- [docker-compose.yml](../docker-compose.yml)
- [configs/model-stack.json](../configs/model-stack.json)
