---
name: reddit-digest
description: "Busca top posts de subreddits de IA e organiza um digest."
metadata:
  openclaw:
    model: usage-router/cerebras/llama3.1-8b
---

# Skill: reddit_digest

Busca os principais posts dos subreddits de IA e organiza um digest personalizado, com curadoria baseada em preferências do usuário.

## Subreddits monitorados
- r/ArtificalIntelligence
- r/ClaudeAI
- r/CursorAI
- r/OpenAI
- r/OpenClawUseCases

## Funcionamento
- Busca os top posts do dia em cada subreddit.
- Salva preferências do usuário em memória separada (memory/reddit_preferences.json).
- Pergunta diariamente se gostou do digest e ajusta as regras de curadoria.
- Exemplo de regra: "do not include memes".
- Pronto para rodar via cronjob diário às 17h.

## Política de busca
- Use Reddit JSON/API pública como fonte principal.
- Não use `web_search` ou Tavily para descobrir posts do Reddit.
- Use `web_fetch` apenas para enriquecer links externos já selecionados no digest final.
- Evite `browser` por padrão.

## Exemplo de saída
```json
[
  {"subreddit": "OpenAI", "title": "OpenAI lança novo modelo...", "url": "https://reddit.com/r/OpenAI/...", "score": 1234}
]
```
