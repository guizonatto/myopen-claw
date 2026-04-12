# Graph Report - .  (2026-04-11)

## Corpus Check
- Large corpus: 200 files · ~84,945 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder, or use --no-semantic to run AST-only.

## Summary
- 590 nodes · 748 edges · 48 communities detected
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 19 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## God Nodes (most connected - your core abstractions)
1. `main()` - 11 edges
2. `main()` - 11 edges
3. `LeadFetcherAgent` - 10 edges
4. `Contato` - 10 edges
5. `Memory` - 10 edges
6. `Base` - 9 edges
7. `normalize_title()` - 9 edges
8. `load_fixture()` - 9 edges
9. `run()` - 8 edges
10. `TextExtractor` - 8 edges

## Surprising Connections (you probably didn't know these)
- `Cronjob: Busca e enriquece leads em SP a cada 30 minutos, priorizando leads com` --uses--> `LeadFetcherAgent`  [INFERRED]
  crons\lead_fetch_and_enrich_cron.py → agents\lead_fetcher\agent.py
- `Filtro para garantir que o autogenerate ignore tabelas de outros schemas.` --uses--> `Base`  [INFERRED]
  mcps\shopping_tracker_mcp\migrations\env.py → mcps\shopping_tracker_mcp\db\models.py
- `Bloqueia qualquer interação com tabelas de outros schemas.` --uses--> `Base`  [INFERRED]
  mcps\trends_mcp\migrations\env.py → mcps\shopping_tracker_mcp\db\models.py
- `LeadFetcherAgent` --uses--> `Contato`  [INFERRED]
  agents\lead_fetcher\agent.py → mcps\crm_mcp\models.py
- `LeadFetcherAgent` --uses--> `Memory`  [INFERRED]
  agents\lead_fetcher\agent.py → mcps\memories_mcp\models.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.04
Nodes (19): BaseModel, _get_engine(), get_session(), _get_session_factory(), Context manager que fornece uma sessão SQLAlchemy com commit/rollback automático, Exporta resumo para Notion. Requer: NOTION_TOKEN, NOTION_DATABASE_ID, Gera resumos semanais (FAQ, CEO, Discord, e-mail, RAG, Notion) a partir dos dado, check_env() (+11 more)

### Community 1 - "Community 1"
Cohesion: 0.07
Nodes (23): LeadFetcherAgent, Agente para busca inteligente de leads em SP, com memória persistente (MCP-Memor, Agente que busca, enriquece e registra leads no CRM, priorizando leads com Whats, Busca memórias relevantes para estratégias e leads já processados., Estratégia dinâmica: consulta memórias, seleciona fontes, busca e enriquece lead, # TODO: lógica para selecionar estratégia vencedora, # TODO: implementar busca real (Google, Instagram, LinkedIn, CNAE, etc.), Busca, enriquece e registra/atualiza leads no CRM, evitando duplicidade e salvan (+15 more)

### Community 2 - "Community 2"
Cohesion: 0.07
Nodes (27): ABC, clean_tweet_text(), GetXApiBackend, _load_id_cache(), load_twitter_sources(), main(), _make_error(), _make_result() (+19 more)

### Community 3 - "Community 3"
Cohesion: 0.05
Nodes (15): load_fixture(), Test that articles are assigned to their highest-priority topic only., Test that duplicate titles across topics are removed., Validate fixture data structure., End-to-end merge with fixture data., Validate merged output structure., TestDeduplication, TestDomainLimits (+7 more)

### Community 4 - "Community 4"
Cohesion: 0.09
Nodes (34): _brave_search_single(), convert_freshness(), detect_brave_rate_limit(), filter_content(), generate_search_interface(), get_brave_api_key(), get_brave_api_keys(), get_tavily_api_key() (+26 more)

### Community 5 - "Community 5"
Cohesion: 0.07
Nodes (25): Função: Cronjob para buscar notícias de negócios e salvar no MCP de negócios Us, Função: Cronjob para buscar editais de inovação e salvar no MCP de negócios Usa, fetch_and_summarize_business_monitor, fetch_and_summarize_edital_monitor, fetch_editais(), fetch_news(), fetch_trends_and_summaries(), Função: Buscar trends do Twitter Brasil e gerar resumo explicativo Usar quando: (+17 more)

### Community 6 - "Community 6"
Cohesion: 0.09
Nodes (32): _b64url(), cmd_trending(), fetch_releases_with_retry(), fetch_trending_repos(), _flush_github_cache(), _generate_github_app_token(), _get_github_cache(), get_repo_name() (+24 more)

### Community 7 - "Community 7"
Cohesion: 0.09
Nodes (32): extract_cdata(), fetch_feed_with_retry(), _flush_rss_cache(), _get_rss_cache(), get_tag(), _load_rss_cache(), load_sources(), main() (+24 more)

### Community 8 - "Community 8"
Cohesion: 0.1
Nodes (32): apply_domain_limits(), apply_previous_digest_penalty(), _build_token_buckets(), calculate_base_score(), calculate_title_similarity(), deduplicate_articles(), _extract_tokens(), get_domain() (+24 more)

### Community 9 - "Community 9"
Cohesion: 0.07
Nodes (11): load_merged_sources(), load_merged_topics(), Load and merge topics from defaults and optional user config overlay.          A, Load and merge sources from defaults and optional user config overlay., User overlay should override matching IDs and add new ones., User overlay with enabled=false should disable a default source., Should work fine with no user config dir., Verify source counts match expectations. (+3 more)

### Community 10 - "Community 10"
Cohesion: 0.15
Nodes (13): crm_mcp, ask_feedback(), curate_digest(), fetch_top_posts(), load_preferences(), Função: Buscar os principais posts dos subreddits de IA e organizar um digest pe, run(), save_preferences() (+5 more)

### Community 11 - "Community 11"
Cohesion: 0.12
Nodes (7): _bulk_mark_accessed(), get_contexto_contato(), get_memory(), get_upcoming_recurrences(), memory_db.py — Backend de memória e relacionamentos do OpenClaw (PostgreSQL + pg, Retorna dados + relacionamentos + memórias + follow-ups em uma única conexão., Retorna memórias recorrentes cuja data cai nos próximos N dias.

### Community 12 - "Community 12"
Cohesion: 0.22
Nodes (8): enrich_articles(), extract_readable_text(), fetch_full_text(), get_domain(), main(), setup_logging(), TextExtractor, HTMLParser

### Community 13 - "Community 13"
Cohesion: 0.22
Nodes (12): load_json_file(), main(), Validate source-type specific requirements., Main validation function., Setup logging configuration., Load and parse JSON file., Validate data against JSON schema., Validate consistency between sources and topics. (+4 more)

### Community 14 - "Community 14"
Cohesion: 0.27
Nodes (11): escape(), is_safe_url(), main(), markdown_to_safe_html(), _process_inline(), Process inline markdown (bold, links, code) with HTML escaping., HTML-escape text content., Validate URL is http(s) only — no javascript:, data:, etc. (+3 more)

### Community 15 - "Community 15"
Cohesion: 0.22
Nodes (6): BaseAgent, Agent: base_agent Função: Template base para agentes que orquestram múltiplos pi, Agente base. Subclasse e implemente `decide_and_run`.     Cada agente tem acesso, Carrega e executa um pipe pelo nome do módulo., Salva uma observação no memory DB., Implemente aqui a lógica do agente.         Exemplo:             data = fetch_so

### Community 16 - "Community 16"
Cohesion: 0.36
Nodes (9): load_health_data(), load_source_file(), load_source_file_flexible(), main(), Load sources from a JSON file, trying 'sources', 'subreddits', and 'topics' keys, report_unhealthy(), save_health_data(), setup_logging() (+1 more)

### Community 17 - "Community 17"
Cohesion: 0.39
Nodes (8): escape(), is_safe_url(), main(), markdown_to_html(), _process_inline(), Process inline markdown with HTML escaping., Convert markdown digest to styled HTML for PDF rendering., wrap_html()

### Community 18 - "Community 18"
Cohesion: 0.36
Nodes (7): build_message(), main(), Build a proper MIME message with HTML body and optional attachment., Send via msmtp (preferred)., Send via sendmail (fallback)., send_via_msmtp(), send_via_sendmail()

### Community 19 - "Community 19"
Cohesion: 0.38
Nodes (6): fetch_subreddit(), load_reddit_sources(), main(), Load Reddit sources from config, with user overrides., Fetch posts from a subreddit using Reddit's JSON API., setup_logging()

### Community 20 - "Community 20"
Cohesion: 0.29
Nodes (4): Template de teste para um pipe. Copie e ajuste para cada novo processo., Substitua 'meu_processo_pipe' pelo nome real do seu pipe., Garante que o pipe não quebra com lista vazia., TestMeuProcessoPipe

### Community 21 - "Community 21"
Cohesion: 0.33
Nodes (5): Testes para tools/telegram_notify.py, send() não deve lançar exceção se a API falhar., send() deve chamar a API do Telegram com a mensagem correta., test_send_calls_telegram_api(), test_send_does_not_raise_on_error()

### Community 22 - "Community 22"
Cohesion: 0.6
Nodes (4): main(), Run a fetch script as a subprocess, return result metadata., run_step(), setup_logging()

### Community 23 - "Community 23"
Cohesion: 0.4
Nodes (1): DummyCompletedProcess

### Community 24 - "Community 24"
Cohesion: 0.5
Nodes (1): Initial migration for trends table

### Community 25 - "Community 25"
Cohesion: 0.5
Nodes (1): Converte coluna embedding de Text para vector(1536) via pgvector

### Community 26 - "Community 26"
Cohesion: 0.5
Nodes (0): 

### Community 27 - "Community 27"
Cohesion: 0.5
Nodes (1): add cnpj and cnaes to contatos  Revision ID: 0004 Revises: 0003 Create Date: 202

### Community 28 - "Community 28"
Cohesion: 0.67
Nodes (3): main(), Print structured summary of merged data., summarize()

### Community 29 - "Community 29"
Cohesion: 0.5
Nodes (3): env_defaults(), Fixtures compartilhadas para todos os testes do OpenClaw.  Uso:   pytest tests/, Garante valores padrão para env vars em todos os testes.

### Community 30 - "Community 30"
Cohesion: 0.5
Nodes (3): Testes para pipes/daily_trends_report_telegram.py, run() deve chamar a skill de trends e a tool de notificação., test_run_orchestrates_skill_and_tool()

### Community 31 - "Community 31"
Cohesion: 0.5
Nodes (3): Testes para skills/twitter_trends.py  Padrão: mockar dependências externas (API,, run() deve retornar lista (mesmo que vazia)., test_run_returns_list()

### Community 32 - "Community 32"
Cohesion: 0.5
Nodes (3): Tool: Discord Notify Envia mensagens para um canal Discord via OpenClaw Gateway, Envia uma mensagem para um canal Discord via OpenClaw Gateway REST API., send_discord_message()

### Community 33 - "Community 33"
Cohesion: 0.67
Nodes (2): Valida se o dicionário tool segue o JSON Schema Draft 7 para Tool., validate_tool_schema()

### Community 34 - "Community 34"
Cohesion: 0.67
Nodes (1): Tool: WhatsApp Baileys Integração de envio/recepção de mensagens WhatsApp via B

### Community 35 - "Community 35"
Cohesion: 1.0
Nodes (1): Script para gerar docs/INDEX.md automaticamente a partir dos arquivos em docs/.

### Community 36 - "Community 36"
Cohesion: 1.0
Nodes (0): 

### Community 37 - "Community 37"
Cohesion: 1.0
Nodes (0): 

### Community 38 - "Community 38"
Cohesion: 1.0
Nodes (0): 

### Community 39 - "Community 39"
Cohesion: 1.0
Nodes (0): 

### Community 40 - "Community 40"
Cohesion: 1.0
Nodes (0): 

### Community 41 - "Community 41"
Cohesion: 1.0
Nodes (0): 

### Community 42 - "Community 42"
Cohesion: 1.0
Nodes (0): 

### Community 43 - "Community 43"
Cohesion: 1.0
Nodes (2): Agent, LeadFetcherAgent

### Community 44 - "Community 44"
Cohesion: 1.0
Nodes (0): 

### Community 45 - "Community 45"
Cohesion: 1.0
Nodes (0): 

### Community 46 - "Community 46"
Cohesion: 1.0
Nodes (1): Fetch tweets for all sources. Returns list of source result dicts.

### Community 47 - "Community 47"
Cohesion: 1.0
Nodes (1): Parse twitterapi.io date format: 'Tue Dec 10 07:00:30 +0000 2024'.

## Knowledge Gaps
- **165 isolated node(s):** `Config`, `Serializa a Tool para dict.`, `Agent: base_agent Função: Template base para agentes que orquestram múltiplos pi`, `Agente base. Subclasse e implemente `decide_and_run`.     Cada agente tem acesso`, `Carrega e executa um pipe pelo nome do módulo.` (+160 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 35`** (2 nodes): `docs_index_script.py`, `Script para gerar docs/INDEX.md automaticamente a partir dos arquivos em docs/.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 36`** (2 nodes): `test_crm_mcp_sse.py`, `test_sse_crm()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 37`** (2 nodes): `test_memories_mcp_sse.py`, `test_sse_memories()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 38`** (2 nodes): `test_shopping_tracker_mcp_sse.py`, `test_sse_shopping()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 39`** (2 nodes): `test_trends_mcp_sse.py`, `test_sse_trends()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 40`** (2 nodes): `test_trending_topics_report.py`, `test_run_pipe()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 41`** (2 nodes): `test_shopping_tracker.py`, `test_skill_shopping_tracker()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 42`** (2 nodes): `test_summarize_trends.py`, `test_run_skill()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 43`** (2 nodes): `Agent`, `LeadFetcherAgent`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 44`** (1 nodes): `test_env.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 45`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 46`** (1 nodes): `Fetch tweets for all sources. Returns list of source result dicts.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 47`** (1 nodes): `Parse twitterapi.io date format: 'Tue Dec 10 07:00:30 +0000 2024'.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Are the 3 inferred relationships involving `LeadFetcherAgent` (e.g. with `Contato` and `Memory`) actually correct?**
  _`LeadFetcherAgent` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 7 inferred relationships involving `Contato` (e.g. with `LeadFetcherAgent` and `Agente para busca inteligente de leads em SP, com memória persistente (MCP-Memor`) actually correct?**
  _`Contato` has 7 INFERRED edges - model-reasoned connections that need verification._
- **Are the 7 inferred relationships involving `Memory` (e.g. with `LeadFetcherAgent` and `Agente para busca inteligente de leads em SP, com memória persistente (MCP-Memor`) actually correct?**
  _`Memory` has 7 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Config`, `Serializa a Tool para dict.`, `Agent: base_agent Função: Template base para agentes que orquestram múltiplos pi` to the rest of the system?**
  _165 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.04 - nodes in this community are weakly interconnected._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.07 - nodes in this community are weakly interconnected._
- **Should `Community 2` be split into smaller, more focused modules?**
  _Cohesion score 0.07 - nodes in this community are weakly interconnected._