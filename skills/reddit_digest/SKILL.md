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

## Exemplo de saída
```json
[
  {"subreddit": "OpenAI", "title": "OpenAI lança novo modelo...", "url": "https://reddit.com/r/OpenAI/...", "score": 1234}
]
```
