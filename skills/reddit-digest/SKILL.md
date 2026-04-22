---
name: reddit-digest
description: "Busca top posts de subreddits de IA e cria um digest diario."
metadata:
  openclaw:
    model: usage-router/cerebras/gpt-oss-120b
---

I want you to give me the top performing posts from the following subreddits.
https://www.reddit.com/r/ArtificalIntelligence/
https://www.reddit.com/r/ClaudeAI/
https://www.reddit.com/r/CursorAI/
https://www.reddit.com/r/OpenAI/
https://www.reddit.com/r/OpenClawUseCases/

Create a separate memory for the reddit processes, about the type of posts I like to see and every day ask me if I liked the list you provided. Save my preference as rules in the memory to use for a better digest curation. (e.g. do not include memes.)
Every day at 5pm, run this process and give me the organized digest

Tool policy:
- Use Reddit JSON/API pages as the default source.
- Do not spend Tavily or generic web search to discover Reddit posts.
- Use `web_fetch` only for external links that were already selected for enrichment.
- Avoid `browser` unless Reddit itself becomes inaccessible through the lightweight path.
