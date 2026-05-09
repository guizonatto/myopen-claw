# Spec — CRM Outbound Agent v2 (Single-Tenant)

Date: 2026-04-25  
Status: Draft para alinhamento antes de implementação  
Escopo desta fase: `single-tenant (Zind)`

## Resumo

Este documento define a arquitetura e os contratos para evolução do agente de outbound em WhatsApp com:

- pipeline anti-tiroteio de mensagens;
- suporte multimodal (áudio inbound com transcrição);
- roteamento por intents para especialistas;
- envio humanizado e follow-up proativo;
- loop de aprendizado com revisão/aprovação humana;
- RBAC explícito e enforcement de camadas.

## Escopo da Fase Atual

Entregas desta fase:

- arquitetura `Router + Specialists` em produção;
- buffer adaptativo de inbound (`completeness + guardrail`);
- transcrição de áudio no ingresso;
- follow-up proativo por silêncio (`24h`, `48h`, `72h`);
- `feedback-reviewer-agent` para revisão com time comercial;
- aprovação humana obrigatória para mudança de estratégia;
- RBAC e allowlist de tools por agente;
- quality gates com verificação de camadas e responsabilidades.

Fora de escopo desta fase:

- isolamento multi-tenant hard (`tenant_id`, RLS, isolamento por coleção/namespace).

## Arquitetura por Camadas (Enforcement Obrigatório)

Camadas oficiais:

1. `ingestion`
2. `context`
3. `routing`
4. `specialists`
5. `actions`
6. `learning`
7. `governance`

Regra de dependência:

- Fluxo permitido: `ingestion -> context -> routing -> specialists -> actions -> learning -> governance`.
- Chamadas reversas entre camadas são proibidas.
- Acesso lateral direto entre especialistas é proibido.
- Toda integração entre camadas deve passar por contratos/eventos públicos.

Política de qualidade:

- violação de camada/responsabilidade é bug bloqueante;
- merge é bloqueado até correção.

## Topologia de Agentes

- `intent-router`: classifica intent e escolhe especialista; não envia mensagem ao lead.
- `qualifier-agent`: qualificação, contexto e enriquecimento orientado à conversa.
- `objection-agent`: tratamento de objeções e battlecards.
- `closing-agent`: avanço para compromisso e agendamento.
- `handover-agent`: transbordo para humano em casos críticos.
- `feedback-reviewer-agent`: conversa com time de vendas, sintetiza aprendizado e propõe ajustes para próximo batch.

## Pipeline Operacional

1. `Inbound` chega pelo canal (texto/áudio).
2. `buffer_incoming_messages` agrega mensagens por completude semântica.
3. Se áudio, `transcribe_incoming_audio` gera texto de contexto (`is_audio=true`).
4. `route_conversation_turn` decide intent, especialista e policy flags.
5. Especialista gera plano de resposta conforme estágio/contexto.
6. `actions` aplica humanização (short messages, split, typing/read delay).
7. Envio é registrado e outcomes atualizam learning.
8. `feedback-reviewer-agent` revisa resultados com humano e gera proposta.
9. Apenas propostas aprovadas entram no próximo batch.

### Debounce Adaptativo (Completeness + Guardrail)

Contrato:

- `buffer_incoming_messages(lead_id, event) -> { payload, flush_reason, grouped_count }`

Regras:

- não fechar por tempo fixo como regra principal;
- fechar quando detectar ideia completa (pergunta/objeção/CTA/contexto suficiente);
- guardrails técnicos: `max_hold_ms=20000`, `max_msgs=6`, `max_chars=1000`;
- flush imediato em sinais fortes.

Garantia:

- um único roteamento por bloco consolidado para evitar respostas duplicadas.

### Multimodal (Áudio)

Contrato:

- `transcribe_incoming_audio(message_id, media_ref) -> { text, confidence }`

Regras:

- `context_builder` injeta `is_audio=true`, `transcript_text`, `audio_duration_sec`;
- resposta padrão permanece texto curto e humano;
- política de áudio outbound fica desativada por padrão nesta fase.

### Humanização WhatsApp

- alvo por mensagem: `140-180` caracteres;
- acima de `220`: quebrar em `2-3` mensagens;
- um objetivo por bloco;
- CTA somente no último chunk;
- aplicar `read_delay` após inbound e `typing_delay` por chunk.

### Follow-up Proativo

Contrato:

- `evaluate_dormant_leads(ruleset) -> { evaluated, triggered }`

Regras:

- injetar eventos internos: `timeout_24h`, `timeout_48h`, `timeout_72h`;
- rotear como intent `proactive_follow_up`;
- após `72h` sem resposta: pausar automação e abrir revisão humana.

## Contratos Públicos (Interfaces)

- `buffer_incoming_messages(lead_id, event) -> { payload, flush_reason, grouped_count }`
- `route_conversation_turn(payload) -> { intent, confidence, specialist, policy_flags }`
- `transcribe_incoming_audio(message_id, media_ref) -> { text, confidence }`
- `evaluate_dormant_leads(ruleset) -> { evaluated, triggered }`
- `start_feedback_review_session(batch_id, stage?, city?, client_type?) -> { session_id }`
- `record_human_feedback(session_id, feedback_text, tags?) -> { saved }`
- `generate_strategy_update_proposal(session_id) -> { proposal_batch_id }`
- `approve_strategy_updates(proposal_batch_id, approver) -> { applied }`
- `reject_strategy_updates(proposal_batch_id, reason) -> { rejected }`

## Learning e Governança

Chave de aprendizado:

- `stage + client_type + city + region + channel + archetype`

Regras:

- ranking com smoothing bayesiano e exploração controlada;
- estratégia com queda contínua entra em cooldown;
- atualização de estratégia em produção exige aprovação humana.

Workflow de proposta:

- `draft_review -> pending_approval -> approved/rejected`

## RBAC (Obrigatório)

Princípios:

- `default deny`;
- menor privilégio;
- separação de deveres;
- auditoria completa para mutações críticas.

Roles:

- `platform_admin`
- `sales_manager`
- `sales_operator`
- `sales_reviewer`
- `automation_runtime`
- `sim_operator`

Matriz de responsabilidades:

- `sales_operator`: operar contato, draft, envio e log; sem aprovações.
- `sales_manager`: aprovar primeiro toque e propostas de estratégia.
- `sales_reviewer`: conduzir review e gerar proposta; sem aplicar em produção.
- `automation_runtime`: executar pipeline técnico; sem decisão de aprovação humana.
- `sim_operator`: operar simulações; sem escrita em learning de produção.
- `platform_admin`: administração de políticas, chaves e overrides controlados.

Allowlist por agente:

- `intent-router`: sem tools de ação externa.
- `qualifier-agent`: tools de enrich/qualify/contexto.
- `objection-agent`: tools de contexto/battlecards.
- `closing-agent`: tools de agenda (`check_calendar`, `book_meeting`).
- `handover-agent`: tool de escalonamento.
- `feedback-reviewer-agent`: leitura de desempenho + proposta; sem apply final.

Auditoria obrigatória:

- registrar `who`, `role`, `operation`, `resource`, `before/after`, `timestamp`, `reason`;
- obrigatório em `approve_first_touch`, `mark_no_interest`, `approve/reject_strategy_updates`.

## Quality Gates Finais (Obrigatórios)

Gate 1 — testes funcionais:

- unit + integração para buffer, áudio, roteamento, envio humanizado, follow-up e reviewer.

Gate 2 — testes de arquitetura:

- detectar chamadas proibidas entre camadas.

Gate 3 — review arquitetural de código:

- checklist explícito para validar ausência de violação de camadas/responsabilidades.

Gate 4 — RBAC/auditoria:

- validar permissões por role e logs de operações críticas.

Definition of Done:

- feature só é concluída com todos os gates aprovados.

## Relação com Docs Anteriores

- Documento canônico desta fase: `docs/specs/crm-outbound-agent-v2/spec-2026-04-25-crm-outbound-agent-v2.md`
- User Stories desta fase: `docs/specs/crm-outbound-agent-v2/US-2026-04-25-crm-outbound-agent-v2.md`
- Technical specs por US: `docs/specs/crm-outbound-agent-v2/TS-2026-04-25-crm-outbound-agent-v2.md`
- `docs/specs/2026-04-23-mcp-crm-enriquecimento-outreach-v1.md` permanece como histórico v1.

## Próxima Fase (Backlog)

- multi-tenant hard isolation:
  - `tenant_id` em entidades e índices;
  - filtros obrigatórios no RAG;
  - RLS/políticas de isolamento no banco;
  - template/prompt isolado por tenant.
