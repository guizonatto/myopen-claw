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

## Referências
- docs/architecture.md
- docs/atomic_rules.md
- .claude/rules/rule-openclaw-new-skill.md

## Padrão obrigatório para Tools MCP
- Toda Tool (operação) registrada em MCP deve declarar explicitamente o campo `input_schema` seguindo JSON Schema v7.
- OinputSchema  deve refletir todos os parâmetros esperados pela operação, incluindo tipos e obrigatoriedade.
- Veja a regra: .claude/rules/rule-mcp-tool-schema.md
