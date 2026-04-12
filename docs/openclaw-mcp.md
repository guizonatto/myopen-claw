# Model Context Protocol (MCP) — OpenClaw

O MCP (Model Context Protocol) é o padrão oficial de integração entre sistemas de IA no ecossistema OpenClaw. Ele define como agentes, skills e serviços externos (como microserviços de IA) se comunicam de forma padronizada, segura e extensível.

## Conceito
- MCP é sempre "Model Context Protocol" em toda a documentação.
- Cada MCP é um serviço/container independente, exposto via HTTP/SSE.
- Skills textuais descrevem operações a serem roteadas para MCPs.

## Estrutura
- MCPs residem em `mcp/`.
- Skills textuais referenciam o MCP executor.
- Orquestração via Docker Compose.

## Exemplo de Skill YAML
```yaml
operation: fetch_trending_topics
mcp: trends_mcp
params:
  region: "BR"
  limit: 10
```

## Exemplo de Endpoint MCP
POST /execute
```json
{
  "operation": "fetch_trending_topics",
  "params": {"region": "BR", "limit": 10}
}
```

## Endpoint SSE HTTP (Streaming)

Cada MCP deve expor um endpoint HTTP para streaming de respostas via Server-Sent Events (SSE), seguindo o padrão:

POST /sse
```json
{
  "operation": "fetch_trending_topics",
  "params": {"region": "BR", "limit": 10}
}
```

**Resposta (SSE):**
```
data: {"status": "started", "operation": "fetch_trending_topics"}

data: {"progress": 33, "msg": "Etapa 1/3", "operation": "fetch_trending_topics"}

data: {"progress": 66, "msg": "Etapa 2/3", "operation": "fetch_trending_topics"}

data: {"progress": 99, "msg": "Etapa 3/3", "operation": "fetch_trending_topics"}

data: {"status": "done", "result": "...resultado final..."}
```

- O endpoint deve usar `media_type: text/event-stream`.
- O cliente pode cancelar a conexão a qualquer momento.
- O fluxo de eventos pode ser customizado conforme a operação.

## Referências
- docs/architecture.md
- docs/atomic_rules.md
- .claude/rules/rule-openclaw-new-skill.md

## Padrão obrigatório para Tools MCP
- Toda Tool (operação) registrada em MCP deve declarar explicitamente o campo `input_schema` seguindo JSON Schema v7.
- OinputSchema  deve refletir todos os parâmetros esperados pela operação, incluindo tipos e obrigatoriedade.
- Veja a regra: .claude/rules/rule-mcp-tool-schema.md
