# OpenClaw Model Configuration Plan (Phase 1)

Date: 2026-04-16

## Goal

Configure a full provider/model stack and pin a primary model per skill, relying only on OpenClaw's built-in model failover (primary + fallbacks). This phase does **not** implement any quota control engine.

## Provider / Model Stack

We use native OpenClaw provider ids wherever possible and only configure explicit provider endpoints when required (e.g., local `ollama`).

### Lane Order (Global Fallback Chain)

1. Groq (free tier) — all free rows frozen from the provider snapshot
2. Google (free tier) — Gemini free rows frozen from the provider snapshot
3. Mistral (free tier) — all free rows frozen from the provider snapshot
4. Cerebras (free tier) — all free rows frozen from the provider snapshot
5. Qwen (paid)
6. DeepSeek (paid)
7. OpenRouter (paid escape hatch)

### Global Default Chain

The generated OpenClaw config sets:

- `agents.defaults.model.primary` = first Groq free model
- `agents.defaults.model.fallbacks` = remaining models in lane order above
- `agents.defaults.models` = curated allowlist used by `/model` UI/CLI selection

### Keys (Env Vars)

- Groq: `GROQ_API_KEY`
- Google Gemini: `GEMINI_API_KEY` (preferred) or `GOOGLE_API_KEY` (if supported by your setup)
- Mistral: `MISTRAL_API_KEY`
- Cerebras: `CEREBRAS_API_KEY`
- Qwen: `QWEN_API_KEY`
- DeepSeek: `DEEPSEEK_API_KEY`
- Ollama local embeddings: existing `OLLAMA_*` and `EMBEDDING_MODEL`

## Per-Skill Model Pinning

Each skill pins a single primary model via frontmatter:

```yaml
metadata:
  openclaw:
    model: groq/llama-3.1-8b-instant
```

If the pinned model is rate-limited/unavailable, OpenClaw falls back through the global chain.

## Skill Mapping (Current)

- Groq fast free: `groq/llama-3.1-8b-instant`
  - `business_monitor`, `business-monitor`, `reddit_digest`, `trends`
- Groq medium free reasoning/tool: `groq/openai/gpt-oss-20b`
  - `crm`, `shopping-tracker`, `vault`, `fetch-trending-topics`
- Groq strongest free reasoning: `groq/qwen/qwen3-32b`
  - `sindico-leads`
- Google heavy research/writing:
  - `edital_monitor` -> `google/gemini-2.5-pro`
  - `daily-content-creator`, `humanizer`, `weekly-michelin-meal-plan`, `usell-sales-workflow` -> `google/gemini-2.5-flash`
- Mistral heavy context/coding:
  - `tech-news-digest` -> `mistral/mistral-large-latest`
  - `github-weekly-summary` -> `mistral/devstral-medium-latest`
  - `curadoria-temas-diarios` -> `mistral/mistral-medium-2508`
- Cerebras heavy reasoning:
  - `politics_economy_monitor` -> `cerebras/qwen-3-235b-a22b-instruct-2507`
  - `reddit-digest` -> `cerebras/gpt-oss-120b`

## Morning Schedule Spread

- `business_monitor_fetch_and_summarize` -> `06:00`
- `edital_monitor_fetch_and_summarize` -> `06:30`
- `politics_economy_monitor_fetch_and_summarize` -> `07:45`
- `tech_news_digest` -> `07:00`
- `morning_brief` -> `07:35`
- `daily_content_creator_ia` -> `08:00`
- `daily_content_creator_condominios` -> `08:15`
- `reddit_digest_fetch_and_curate` -> `17:00`
- `github_weekly_summary` -> quinta `15:00`

## Repo Artifacts

This plan is implemented by:

- `configs/model-stack.json` (source of truth: lane order, model lists, skill mapping)
- `scripts/apply-model-stack.mjs` (generator: materializes the stack into `openclaw.json`)
- Bootstrap changes in `entrypoint.sh` so the generated config persists through onboarding/restarts

## Search / Browser Policy

Search/browsing is configured per skill with a cheap global floor:

- Global `tools.web.search.provider` defaults to `duckduckgo`
- `tools.web.fetch.enabled = true`
- `browser.enabled = true`, but browser is reserved for JS-heavy/login/interact cases
- `TAVILY_API_KEY` is used selectively, not as the gateway-wide default

### Tool ladder

1. `web_fetch` for known URLs and fixed source lists
2. `web_search` with DuckDuckGo for cheap discovery
3. Tavily only for focused, higher-value research
4. Browser only for JS-heavy or login-gated pages

### Search mapping by skill

- `business-monitor` -> `web_fetch` first; `web_search` only if a source moves or blocks
- `edital_monitor` -> `web_fetch` first; domain-scoped `web_search`; browser only for JS listings
- `politics_economy_monitor` -> `web_fetch` + selective `web_search`; Tavily only as exception
- `curadoria-temas-diarios` -> `web_search` (`duckduckgo`) + `web_fetch`; Tavily only for AI, tecnologia, startups/negócios, ciência
- `daily-content-creator` -> Tavily + `web_fetch`; browser only for LinkedIn or JS/login pages
- `tech-news-digest` -> RSS/GitHub/Reddit direct first; Tavily for `fetch-web.py`; browser out of normal path
- `fetch-trending-topics` / `x-trending` -> browser only
- `trends` -> `web_fetch` on `trends24.in`; browser only if needed
- `reddit-digest` / `reddit_digest` -> Reddit JSON/API, optional `web_fetch` for chosen external links
- `github-weekly-summary` -> no `web_search`/`browser`
- `sindico-leads` -> `web_search` (`duckduckgo`) + `web_fetch`; Tavily only for shortlist enrichment; browser only for LinkedIn/Instagram/JS directories

## Verification Checklist

- `openclaw.json` default model chain starts at Groq and no longer defaults to NVIDIA/OpenRouter/Ollama.
- OpenRouter and Hugging Face are removed from the active free lane and remain only as paid escape-path documentation if needed later.
- Skills have valid YAML frontmatter and pinned models per mapping above.
- Removing one provider key forces fallback to the next lane without manual intervention.
- memclaw embeddings still use local Ollama (`embeddingApiBaseUrl` points to `host.docker.internal:11434/v1`).
