# MCP-CRM Enriquecimento, Prontidão e Conversa Humana (v1)

Date: 2026-04-23

## Objetivo

Consolidar o fluxo de CRM para evitar contato frio, melhorar qualidade de dados e garantir abordagem humana com auditoria.

Fluxo principal:

`ingested -> verified -> enriched -> qualified -> awaiting_approval -> approved -> contacted -> follow_up`

Bloqueio definitivo:

- Se cliente sinalizar desinteresse, marcar `do_not_contact=true`, mover para `pipeline_status=perdido` e impedir novos envios.

## Campos novos em `contatos`

- `readiness_status`, `readiness_score`, `verified_signals_count`
- `last_enriched_at`, `fresh_until`, `needs_human_review`
- `do_not_contact`, `do_not_contact_reason`, `do_not_contact_at`
- `persona_profile`, `pain_hypothesis`, `recent_signal`, `offer_fit`, `preferred_tone`, `best_contact_window`
- `city`, `region`, `client_type`
- `inferred_city`, `inferred_region`, `inferred_client_type` (flags de fallback por inferência)

## Novas entidades

- `contact_enrichment_runs`: histórico de enriquecimento (fonte, confiança, divergências, evidências)
- `contact_interactions`: timeline por canal/direção/resultado
- `contact_tasks`: agendamento de próximos passos, dono, prioridade e SLA
- `calendar_links`: rastreio de sincronização com Google Calendar
- `message_strategy_outcomes`: eventos de resultado por estratégia/mensagem enviada
- `message_strategy_rankings`: agregado por chave de aprendizado com score Bayesiano e confiança

## Operações MCP adicionadas

- `verify_contact_data`
- `enrich_contact_data(mode="deep")`
- `qualify_contact_for_outreach`
- `create_personalized_outreach_draft`
- `approve_first_touch`
- `schedule_contact_task(sync_calendar=true)`
- `sync_calendar_links`
- `log_conversation_event`
- `mark_no_interest`
- `send_daily_improvement_report`
- `send_whatsapp_outreach`

Compatibilidade preservada:

- `add_contact`
- `search_contact`
- `update_contact`
- `list_contacts_to_follow_up`

Extensões compatíveis de payload:

- `create_personalized_outreach_draft` retorna:
  - `messages[]`, `split_applied`
  - `strategy_key`, `message_archetype`, `confidence`
  - `checks` de humanidade/compliance
- `log_conversation_event` aceita metadados de estratégia para fechar o loop de aprendizado.
- `send_whatsapp_outreach` aceita:
  - `draft_interaction_id` (reuso do draft aprovado)
  - `messages[]` (override explícito)
  - `require_approved` (default true)

## Envio WhatsApp com presença humana

- O envio real de WhatsApp deve simular digitação humana antes de cada chunk.
- Quando houver mensagem inbound anterior (reply do lead), aplicar tempo de leitura humana antes de iniciar a digitação.
- Padrão primário (Evolution API):
  - endpoint: `POST /message/sendText/{EVOLUTION_INSTANCE}`
  - body: `options.presence=\"composing\"` + `options.delay=<delay_ms>`
- Fórmula de delay:
  - `base = len(message) * 40ms`
  - `jitter = [-400ms, +600ms]`
  - `clamp = [1500ms, 8000ms]`
- Fórmula de leitura (pré-envio):
  - `base = len(incoming_text) * 55ms`
  - `jitter = [-500ms, +900ms]`
  - `clamp = [1200ms, 12000ms]`
- Aplicação do delay de leitura:
  - calcular `target_read_delay_ms`
  - medir `elapsed_since_inbound_ms` quando houver inbound recente
  - aplicar `max(target_read_delay_ms - elapsed_since_inbound_ms, 0)`
- Para mensagens em bloco (`messages[]`), aplicar delay por chunk.
- Fallback operacional:
  - se Evolution não estiver configurado, usar gateway (`tools/invoke` ou `/api/message`)
  - manter delay local antes de cada envio para preservar timing humano.

## Readiness score e penalidades

Fórmula:

`readiness_score = clamp(0, 100, positive_score - penalty_score)`

Blocos positivos:

- `contactability` (0-25)
- `verification` (0-20)
- `icp_fit` (0-20)
- `freshness` (0-15)
- `pain_signal` (0-10)
- `intent_signal` (0-10)

Penalidades conservadoras:

- Divergência WhatsApp: `-20`
- Divergência Email: `-12`
- Divergência Empresa/CNPJ: `-10`
- Cap do bloco de divergência: `-30`
- Confiança `< 0.65`: `-10`
- Confiança `< 0.50`: `-18`
- Frescor 8-14 dias: `-8`
- Frescor 15-30 dias: `-15`
- Frescor >30 dias: `-25`
- Sem hipótese de dor: `-6`
- Sem ICP: `-8`
- Sem janela preferida: `-4`
- 2 tentativas sem resposta: `-8`
- 3 tentativas sem resposta: `-15` e sugestão de `pipeline_status=perdido`

Hard blocks:

- `do_not_contact=true`
- Sem canal válido

Gate obrigatório para 1o contato:

- `readiness_score >= 70`
- `verified_signals_count >= 2`
- `fresh_until >= now`
- `do_not_contact = false`
- canal válido (prioridade para WhatsApp)

## Motor de conversa humana

Arquitetura:

- Skill única orquestradora (CRM) + biblioteca versionada em `skills/crm/library/`.

Biblioteca:

- `identity_soul.json`
- `stage_playbook.json`
- `battlecards.json`
- `human_rules.json`

Fluxo de mensagem:

1. Ler estágio/histórico no CRM
2. Selecionar objetivo e CTA do estágio
3. Gerar draft personalizado com contexto do contato
4. Executar checks de humanidade/compliance
5. Colocar em fila de aprovação para 1o toque
6. Registrar interação e atualizar estado

## Humanization Rules (WhatsApp)

- Humanos escrevem mensagens curtas no WhatsApp.
- Tamanho alvo por mensagem: 140-180 caracteres.
- Se o conteúdo bruto ultrapassar 220 caracteres, o sistema deve quebrar em 2-3 mensagens sequenciais.
- Cada bloco deve manter um único objetivo de comunicação.
- CTA deve aparecer apenas na mensagem final do bloco.
- Regras anti-bot obrigatórias:
  - sem textão único
  - sem linguagem robótica/genérica
  - sem promessa vaga de marketing
  - com contexto real do lead na abertura

Playbooks operacionais (lead / WhatsApp):

- `human_direct_probe_3step` (contato humano direto, sem indício de bot):
  1. `Ola {nome}, tudo bem?`
  2. `Vi seu contato no Google.`
  3. `Voce ainda atende como sindico profissional?`
- Objetivo: abrir conversa com baixa friccao e validar rapidamente se o contato correto ainda atende.
- Características: mensagens curtas, uma intenção por mensagem, sem pitch longo no primeiro bloco.

- `bot_router_vendor_pitch` (quando inbound indicar bot/portaria/URA, por exemplo pedindo bloco/unidade):
  - mensagem única mais completa, contextualizando que somos fornecedores para síndicos profissionais.
  - incluir CTA para envio de materiais de prova:
    - vídeo curto
    - site da Zind
    - 3 artigos do blog da Zind
- Objetivo: passar pelo gate do bot/portaria com contexto suficiente, evitando sequência de mensagens curtas que tende a ser bloqueada.

Detecção de bot/portaria (v1):

- baseada no último inbound por WhatsApp (`content_summary`) com palavras-chave como:
  - `bloco`, `unidade`, `apartamento`, `apto`, `torre`, `portaria`, `identifique`, `digite`
- quando detectar, o draft deve forçar `message_archetype=bot_router_vendor_pitch`.
- sem detecção e em primeiro toque `stage=lead`, priorizar `message_archetype=human_direct_probe_3step`.

## Learning by Stage/Client Type/City

- Unidade de aprendizado (strategy key):
  - `stage + client_type + city + channel + message_archetype`
- Base inicial (seed) versionada:
  - `skills/crm/library/message_strategy_seed.json`
- Ordem de recuperação da estratégia:
  1. chave exata
  2. wildcard de cidade
  3. wildcard de cidade + canal
  4. fallback global por estágio
  5. fallback semântico leve (similaridade lexical/tags; sem embeddings na v1)

Comportamento de seleção:

- Exploração ativa com epsilon-greedy (`epsilon=0.15`)
- Sem histórico suficiente: priorizar seed + marcar baixa confiança

## Outcome Scoring & Ranking

Score ponderado por outcome (por mensagem enviada):

- `+3` reply
- `+5` stage advance por hop
- `+6` meeting scheduled
- `-2` no reply (first SLA window)
- `-4` no reply (second SLA window)
- `-10` explicit no-interest

Ranking:

- Método: Bayesian-smoothed score com prior weight.
- Exploração: epsilon-greedy com `epsilon=0.15`.
- Confiança:
  - estratégia com amostra baixa deve ser marcada como low confidence
  - estratégia de baixa confiança não deve dominar seleção automática

Regras operacionais de janela SLA:

- `first no-reply window`: após `sla_hours` (default 24h) sem resposta
- `second no-reply window`: após `2 * sla_hours` sem resposta

Modelo sugerido para score suavizado:

- `smoothed_score = (prior_weight * prior_mean + total_outcome_points) / (prior_weight + attempts)`
- defaults v1:
  - `prior_mean = 0.0`
  - `prior_weight = 5`

## Data Requirements for Learning

- Campos explícitos no CRM são fonte de verdade:
  - `city`
  - `region`
  - `client_type`
- Fallback por inferência é permitido apenas quando o dado explícito estiver ausente.
- Sempre registrar flag de inferência para auditoria (`inferred_city`, `inferred_region`, `inferred_client_type`).

## Daily Improvement Report (Discord)

- Canal oficial: `sales-bot-improvement`.
- Frequência: 2 envios por dia (12:00 e 19:00 BRT).
- Conteúdo do relatório:
  - top 5 estratégias
  - bottom 5 estratégias
  - winners/losers por stage/client_type/city
  - recomendações concretas de tuning da conversa
- Saída deve respeitar chunking seguro para Discord quando exceder limite de tamanho.
- Deve suportar envio direto por Discord API (bot token) e fallback via gateway.
- Worker dedicado com CLI para execução por cron.

## Agendamento e calendar

- Toda ação de agendamento gera registro em `contact_tasks`
- Quando `sync_calendar=true`, cria vínculo em `calendar_links` com status inicial `pending_sync`
- Worker real Google Calendar:
  - operação MCP `sync_calendar_links`
  - CLI `python -m mcps.crm_mcp.calendar_sync_worker --limit 20`
  - status processados: `pending_sync`, `failed_sync`, `all`
  - usa service account via `GOOGLE_SERVICE_ACCOUNT_JSON` ou `GOOGLE_SERVICE_ACCOUNT_FILE`
  - usa `GOOGLE_CALENDAR_ID` (default `primary`) e opcional `GOOGLE_CALENDAR_IMPERSONATE_USER`

## Discord Sales Simulation Mode

Objetivo:

- Simular conversa comercial no Discord com dois agentes independentes:
  - `sales-sim` (vendedor)
  - `sindico-sim` (cliente simulado)
- Orquestração feita por `sim-control`.

Contrato de comando manual:

- `sim start city=<cidade> stage=<estagio> persona="<perfil_sindico>" [difficulty=<easy|medium|hard>]`

Fluxo:

1. `sim-control` valida comando e parâmetros.
2. Cria thread no mesmo canal pai.
3. Abre sessões isoladas por run:
   - `agent:sales-sim:session:sim:<run_id>:sales`
   - `agent:sindico-sim:session:sim:<run_id>:client`
4. Alterna turnos entre vendedor e cliente.
5. `sindico-sim` retorna JSON estruturado:
   - `reply`, `end`, `end_reason`, `objection_type`, `sentiment`
6. Se JSON inválido, aplicar 1 retry "JSON-only"; se falhar novamente, abortar com diagnóstico.
7. Publicar transcript completo na thread e resumo conciso no canal pai.

Isolamento obrigatório:

- workspaces separados para `sales-sim` e `sindico-sim`
- `memorySearch.enabled=false` para ambos
- deny de tools de sessão cruzada (`sessions_send`, `sessions_spawn`, `sessions_history`)
- sem acesso de escrita em CRM de produção no modo simulação

Persistência:

- salvar artefatos em storage de simulação separado:
  - metadata de run
  - transcript completo
  - outcomes (funcionou/não funcionou, objeções, fechamento)

Regra de impacto em produção:

- simulação **não atualiza** `message_strategy_outcomes`/`message_strategy_rankings` de produção.
- uso exclusivo para análise e tuning manual.

## Zind Brand Guardrail + Memory Sources

- O `sales-sim` deve representar **exclusivamente a Zind**.
- É proibido citar outra empresa/marca como se fosse a empresa do vendedor.
- O prompt do `sales-sim` deve incluir contexto curto vindo do Vault da Zind (fonte canônica):
  - alvo primário: `2000-Knowledge/Empresas/Zind/ZIND_MOC.md`
  - apoio: `2000-Knowledge/Empresas/Zind/PITCH_VENDAS.md`
  - fallback: `0000-Atlas/Zind.md`
- Contexto injetado deve ser resumido e limitado (evitar inflar token).
- Persistir em metadata da simulação:
  - `zind_context_sources` (arquivos usados no prompt)
  - `memory_health` com status de:
    - `vault_has_zind_context`
    - `qdrant_has_zind_context` (amostragem de payloads)
    - `qdrant_collections`
- Se Qdrant não tiver evidência de conteúdo Zind, a simulação continua usando Vault e registra aviso em metadata.

### Qdrant Sync (Zind Context)

- Objetivo: garantir que o conteúdo comercial da Zind também esteja vetorizado no Qdrant.
- Comportamento:
  - ler arquivos de contexto da Zind no Vault
  - quebrar em chunks curtos
  - gerar embedding por chunk (com fallback determinístico quando embedding externo não estiver disponível)
  - fazer upsert idempotente em coleção Qdrant preferencial (`cortex_memories_tenant_claw`, fallback `cortex_memories`)
- IDs devem ser determinísticos por `source_path + chunk_index` para evitar duplicação.
- Payload mínimo por ponto:
  - `brand="zind"`
  - `source="zind_vault_sync"`
  - `source_path`
  - `chunk_index`
  - `content`
  - `created_at`
- Resultado da sincronização deve ser salvo em metadata (`zind_qdrant_sync`) com:
  - coleção escolhida
  - dimensão vetorial
  - quantidade de pontos upsertados
  - warnings/erros

## Token Efficiency Guardrails (Simulation)

- Objetivo: reduzir custo de token e ruído no prompt dos agentes de simulação.
- Regras:
  - remover aliases MCP legados (`crm`, `shopping`, `trends`) para evitar duplicação de tools no runtime
  - manter apenas IDs canônicos (`mcp-crm`, `mcp-shopping`, `mcp-trends`, `mcp-leads`)
  - configurar `sim-control`, `sales-sim` e `sindico-sim` com `tools.profile="messaging"`
  - manter `allow/deny` mínimo por agente (privilégio mínimo)
  - executar reconciliação pós-onboarding para limpar sobras de configuração no mesmo boot
- Resultado esperado:
  - menos schema injetado no system prompt
  - menor consumo de tokens por turno
  - menor risco de “vazamento” de contexto não necessário

## Tracker de implementação

- [x] Modelo de prontidão (`readiness_score`, penalidades, hard blocks)
- [x] Pipeline de estado operacional (`ingested` até `follow_up` + bloqueio)
- [x] Draft humano com biblioteca versionada (`identity_soul`, `playbook`, `battlecards`, `human_rules`)
- [x] Aprovação humana do 1o toque
- [x] Bloqueio definitivo em desinteresse (`mark_no_interest`)
- [x] Tarefas de contato + vínculo calendário (`contact_tasks`, `calendar_links`)
- [x] Worker real de sync Google Calendar (`sync_calendar_links` + CLI worker)
- [x] Testes unitários de score/estado e de cliente/payload do sync calendar
- [x] WhatsApp short-message splitter (<=220 sem split, >220 com split em 2-3 mensagens)
- [x] Seed de estratégia + retrieval precedence por stage/client_type/city/channel/archetype
- [x] Weighted scorer + ranking Bayesiano + exploração epsilon-greedy
- [x] Worker de relatório diário em Discord (`sales-bot-improvement`, 12:00 e 19:00 BRT)
- [x] Testes de humanização + ranking + reporting
- [x] Envio WhatsApp com simulação de digitação humana (`presence=composing` + delay por chunk)
- [x] Simulação Discord com dois agentes isolados (`sales-sim` x `sindico-sim`) e orquestrador `sim-control`
- [x] Runner manual `sim start ...` com thread + transcript + resumo final
- [x] Persistência separada de simulação sem impacto no learning de produção
- [x] Guardrails de eficiência de token na simulação (perfil `messaging` + limpeza de aliases MCP + reconcile pós-onboarding)
- [x] Guardrail de marca Zind no `sales-sim` (sem desvio para marcas externas)
- [x] Injeção de contexto comercial da Zind via Vault no prompt de simulação
- [x] Diagnóstico de cobertura de memória (Vault + Qdrant) salvo na metadata da simulação
- [x] Sincronização idempotente de contexto Zind no Qdrant durante execução de simulação

## Test Plan (Pre-Implementation Documentation)

Unit:

- split rules (`<=220` sem split, `>220` com split)
- retrieval precedence por chave de estratégia
- weighted score math
- ranking confidence behavior

Integration:

- `draft -> send -> outcome log -> rank update -> next selection`
- no-interest bloqueia contato e penaliza estratégia
- geração de relatório com chunking seguro para Discord

Acceptance:

- sem textão único no WhatsApp
- ranking evolui por stage/client_type/city
- dois relatórios diários no Discord com sugestões acionáveis

## Assumptions

- Arquivo canônico de spec permanece:
  - `docs/specs/2026-04-23-mcp-crm-enriquecimento-outreach-v1.md`
- Qualquer spec duplicada deve ser removida/deprecada após merge no arquivo canônico.
- Nenhuma implementação funcional adicional deve começar antes da revisão desta atualização de spec.

## Roadmap pós-v1

- owner obrigatório por etapa e SLA operacional por estágio
- dashboard de qualidade (quente/frio/verificado/bloqueado)
- A/B de mensagens por segmento
- catálogo padrão de motivos de perda e bloqueio
