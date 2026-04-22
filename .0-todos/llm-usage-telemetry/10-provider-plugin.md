# Módulo 1 — Provider Plugin

Status: `completed`

## Responsabilidade
- Registrar o provider local `usage-router`.
- Aceitar modelos no formato `usage-router/<provider>/<model>`.
- Encaminhar requisições do gateway ao proxy com contexto interno.

## Interface
- Entrada: seleção de modelo do OpenClaw.
- Saída: chamadas OpenAI-compatible para `MODEL_USAGE_PROXY_URL` com base normalizada em `/openclaw/v1`.
- O service do chamador é inferido do path (`/openclaw/...`); headers internos continuam suportados como fallback no proxy.
- `payload.model` preserva o model ref `usage-router/<provider>/<model>`.

## Checklist
- [x] Criar pacote do plugin em `plugins/usage-router-plugin/`
- [x] Implementar parsing do model ref
- [x] Implementar entrypoint do provider plugin
- [x] Definir instalação automática no `entrypoint.sh`
- [x] Registrar interface exata plugin → proxy no índice
- [x] Adicionar teste de parsing/model ref

## Evidências
- `plugins/usage-router-plugin/index.js` registra o provider dinâmico `usage-router`.
- `plugins/usage-router-plugin/src/model-ref.js` faz parse e normalização do ref `usage-router/<provider>/<model>`.
- `entrypoint.sh` instala o plugin local em `/root/.openclaw/extensions/usage-router`.
- Verificado com:
  - `node --test plugins/usage-router-plugin/tests/model-ref.test.js`
  - `node --check plugins/usage-router-plugin/index.js`
