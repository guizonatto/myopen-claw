---
name: business-monitor
description: "Monitora fontes de noticias de negocios e gera resumos."
metadata:
  openclaw:
    model: usage-router/groq/llama-3.1-8b-instant
---

# Skill: fetch_and_summarize_business_news

Monitora fontes de notícias de negócios nacionais e internacionais e gera resumos automáticos.

## Fontes monitoradas
- Exame PME: https://exame.com/pme/
- Startups.com.br: https://startups.com.br/
- Endeavor Brasil: https://endeavor.org.br/
- TechCrunch: https://techcrunch.com/
- Reuters Business: https://www.reuters.com/business/
- Morning Brew: https://www.morningbrew.com/daily
- HackerNews: https://thehackernews.com/
- Product Hunt: https://www.producthunt.com/

## Funcionamento
- Busca as principais manchetes de cada fonte (heurística simples).
- Gera um resumo automático para cada notícia.
- Pronto para integração com MCP de negócios.

## Política de busca
- Use `web_fetch` como caminho padrão para cada fonte fixa acima.
- Só use `web_search` para reencontrar uma página quando a URL mudar, a estrutura quebrar ou a fonte bloquear o fetch direto.
- Evite Tavily por padrão nesta skill.
- Evite `browser` salvo se uma fonte passar a exigir JavaScript para exibir as manchetes.

## Exemplo de saída
```json
[
  {"fonte": "Exame PME", "titulo": "Startup X capta R$ 10 milhões...", "url": "https://exame.com/pme/", "summary": "Resumo automático: 'Startup X capta R$ 10 milhões...' é destaque em Exame PME."}
]
```
