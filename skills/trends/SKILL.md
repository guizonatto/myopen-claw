---
name: trends
description: "Busca trending topics e gera resumos."
metadata:
  openclaw:
    model: usage-router/groq/llama-3.1-8b-instant
---

# Skill: fetch_and_summarize

Busca os trending topics do Twitter Brasil em https://trends24.in/brazil/ e gera um resumo explicativo para cada trend.

- Salva os resultados no MCP trends_mcp (endpoint esperado: /trends ou similar).
- Cada trend recebe um campo 'summary' para contexto.
- Usar em conjunto com cronjob para atualização periódica.

## Política de busca
- Use `web_fetch` diretamente em `https://trends24.in/brazil/`.
- Só use `browser` se a página deixar de renderizar o conteúdo necessário sem JavaScript.
- Não use Tavily nesta skill.

## Exemplo de saída

```json
[
  {"trend": "#BBB26", "summary": "Resumo automático: '#BBB26' é um dos assuntos mais comentados no Twitter Brasil no momento."},
  {"trend": "Lula", "summary": "Resumo automático: 'Lula' é um dos assuntos mais comentados no Twitter Brasil no momento."}
]
```

## Referências
- https://trends24.in/brazil/
- docs/openclaw-mcp.md
