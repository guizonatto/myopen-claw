# Technical Specs by User Story — CRM Outbound Agent v2

Date: 2026-04-25  
Scope: `single-tenant (Zind)`  
Base docs: `docs/openclaw_reference.md`, `docs/openclaw-multiagent.md`, `docs/config_reference.md`, `docs/webhooks.md`

## 1) Baseline Técnico (OpenClaw)

Arquitetura base para esta fase:

- Gateway OpenClaw como frontdoor de canais (`channels.whatsapp`, `channels.discord`).
- Roteamento por `bindings` + agente de entrada dedicado para fluxo de vendas.
- Sessões isoladas por peer (`session.dmScope=per-channel-peer`).
- Agentes especializados com `tools.profile` + `allow/deny` por agente.
- Ingress por mensagem de canal e fila interna de eventos de domínio.
- `/hooks/agent` é fallback operacional opcional, não caminho primário.
- Observabilidade via logs de gateway + eventos de domínio do CRM.

Regras de hardening aplicadas da doc OpenClaw:

- `default deny` no nível de tool policy.
- deny explícito de tools de sessão cruzada quando não necessárias.
- allowlist de agentes para hooks (`hooks.allowedAgentIds`) quando for usar webhook ingress.
- `hooks.allowRequestSessionKey=false` por padrão global.
- Se fallback por hooks for habilitado para follow-up proativo, permitir session key por requisição apenas com prefixo estrito por lead.

## 2) Componentes e Responsabilidade

- `sales-ingress-agent` (novo): intake de inbound, debounce semântico e normalização.
- `intent-router-agent` (novo): classifica intent, estágio e escolhe especialista.
- `qualifier-agent` (novo): diagnóstico inicial/qualificação.
- `objection-agent` (novo): resposta de objeções.
- `closing-agent` (novo): encaminhamento para agenda/compromisso.
- `handover-agent` (novo): escalonamento para humano.
- `feedback-reviewer-agent` (novo): revisão com time comercial e geração de propostas.
- `proactive-followup-worker` (novo): eventos 24/48/72 de silêncio.
- `crm-mcp` (existente): source of truth para contato, interações, ranking, propostas.

## 3) Technical Spec por US

## Epic 1 — Ingestion/Buffer Anti-Tiroteio

### US-1.1 — Consolidar rajadas antes do roteamento
Implementação técnica:

- Adicionar pipeline `buffer_incoming_messages(lead_id, event)` no `sales-ingress-agent`.
- Persistir estado transitório do buffer por `lead_id` (janela ativa + mensagens pendentes).
- Emitir evento interno `turn.buffered_ready` para o roteador.

Config OpenClaw:

- Binding do WhatsApp de vendas para `sales-ingress-agent`.
- `session.dmScope=per-channel-peer` para evitar mistura entre contatos.

Testes técnicos:

- rajada de 3 mensagens => 1 evento `turn.buffered_ready`;
- verificação de idempotência por `message_id`.

### US-1.2 — Flush por completude + guardrails
Implementação técnica:

- Classificador leve de completude no ingress:
  - sinais: pergunta explícita, objeção fechada, CTA recebido.
- Guardrails técnicos:
  - `max_hold_ms=20000`
  - `max_msgs=6`
  - `max_chars=1000`
- `flush_reason` obrigatório no payload (`semantic_complete|guardrail_time|guardrail_count|guardrail_size`).

Testes técnicos:

- completude detectada => flush imediato;
- sem completude + limite => flush por guardrail.

### US-1.3 — Uma execução ativa por lead
Implementação técnica:

- Lock distribuído por `lead_id` no ingress.
- Fila curta por lead para eventos concorrentes.
- Retry com backoff para lock contention.

Testes técnicos:

- dois eventos simultâneos do mesmo lead => 1 execução ativa;
- sem duplicidade de outbound.

## Epic 2 — Multimodal + Humanização

### US-2.1 — Áudio inbound com transcrição
Implementação técnica:

- Middleware `transcribe_incoming_audio(message_id, media_ref)`.
- Normalização em `context_builder`:
  - `is_audio=true`
  - `transcript_text`
  - `audio_duration_sec`
  - `transcript_confidence`

Config OpenClaw:

- canal WhatsApp com mídia habilitada;
- fallback seguro quando transcrição falhar (marcar erro e seguir com prompt de confirmação curta).

Testes técnicos:

- áudio válido => transcrição registrada;
- falha de transcrição => fallback sem quebrar turno.

### US-2.2 — Mensagens curtas e split
Implementação técnica:

- Enforcement no motor de draft:
  - alvo 140-180 chars por chunk;
  - `>220` => split em 2-3 mensagens;
  - CTA só no último chunk.
- Check `anti_text_wall` obrigatório em `checks`.

Testes técnicos:

- payload <=220 sem split;
- payload >220 com split e CTA final.

### US-2.3 — Read delay + typing delay
Implementação técnica:

- Antes do 1º chunk outbound: aplicar `read_delay` com base no inbound.
- Por chunk: aplicar `typing_delay` antes do envio.
- Implementar via provider primário (presence/composing) com fallback gateway.

Testes técnicos:

- presença ativa por chunk quando provider suporta;
- fallback aplica delay local quando provider não suporta.

## Epic 3 — Follow-up Proativo

### US-3.1 — Eventos 24h/48h/72h
Implementação técnica:

- Worker `evaluate_dormant_leads` (cron):
  - identifica contatos sem reply por janela SLA;
  - injeta evento interno no pipeline por fila de domínio (`system_event`), sem entrega direta ao canal.
- Fallback opcional via `/hooks/agent` somente quando a fila interna estiver indisponível:
  - `agentId="sales-ingress-agent"`
  - `sessionKey="hook:followup:<lead_id>"`
  - `deliver=false`
  - sem `channel`/`to` no payload do hook
- O envio ao lead só pode ocorrer no estágio `actions`, com destinatário determinístico do CRM.

Config OpenClaw:

- Modo padrão desta fase: sem dependência obrigatória de webhook ingress para follow-up.
- Se fallback por hooks for habilitado:
  - `hooks.enabled=true`
  - `hooks.token` dedicado
  - `hooks.allowedAgentIds=["sales-ingress-agent"]`
  - `hooks.allowRequestSessionKey=true`
  - `hooks.allowedSessionKeyPrefixes=["hook:followup:"]`
  - `hooks.defaultSessionKey` não deve ser compartilhado entre leads de follow-up.

Testes técnicos:

- contato mudo 24h => gera `timeout_24h`;
- mesma lógica para 48h e 72h.
- validar isolamento de sessão por lead no fallback hooks.
- validar que evento de follow-up interno nunca dispara envio para `last recipient`.

### US-3.2 — Pausa após 72h
Implementação técnica:

- Regra no worker: após `timeout_72h`, mudar estado para pausa e abrir tarefa de revisão.
- Bloquear novos follow-ups automáticos enquanto status de pausa estiver ativo.

Testes técnicos:

- após 72h sem resposta => sem novo ping automático;
- tarefa de revisão humana criada.

## Epic 4 — Feedback Reviewer + Aprovação Humana

### US-4.1 — Sessão de review em Discord
Implementação técnica:

- `feedback-reviewer-agent` recebe comando/trigger do batch.
- Publica abertura de thread no canal `sales-bot-improvement`.
- Coleta feedback em formato estruturado (`feedback_text`, tags opcionais).

Config OpenClaw:

- binding de canal Discord de melhoria para `feedback-reviewer-agent`.
- tools profile `messaging` + allowlist de leitura/consulta e criação de proposta.

Testes técnicos:

- batch fechado => thread criada + sessão registrada;
- feedback registrado no CRM com referência de sessão.

### US-4.2 — Aprovação/rejeição de proposta
Implementação técnica:

- Workflow:
  - `generate_strategy_update_proposal` cria `proposal_batch_id`.
  - `approve_strategy_updates` aplica alterações.
  - `reject_strategy_updates` encerra proposta sem apply.

RBAC:

- apenas `sales_manager` pode aprovar/rejeitar.

Testes técnicos:

- proposta sem aprovação não altera seleção;
- proposta aprovada altera seleção do próximo batch.

### US-4.3 — Rastreabilidade de status
Implementação técnica:

- Status machine:
  - `draft_review`
  - `pending_approval`
  - `approved`
  - `rejected`
- registrar transições com auditoria completa.

Testes técnicos:

- transições inválidas bloqueadas;
- trilha de auditoria íntegra.

## Epic 5 — RBAC e Auditoria

### US-5.1 — Autorização por role
Implementação técnica:

- Policy engine no gateway/app layer:
  - mapping role -> operações permitidas.
- `default deny` para operação sem regra explícita.

Testes técnicos:

- role sem permissão => `denied` + audit log;
- role correta => operação permitida.

### US-5.2 — Auditoria de ações críticas
Implementação técnica:

- Log obrigatório para operações críticas:
  - `approve_first_touch`
  - `mark_no_interest`
  - `approve_strategy_updates`
  - `reject_strategy_updates`
- Campos mínimos:
  - `who`, `role`, `operation`, `resource_id`, `reason`, `timestamp`, `before`, `after`.

Testes técnicos:

- tentativa sem `reason` em operação crítica => bloquear;
- evento aprovado gera trilha completa.

### US-5.3 — Allowlist de tools por agente
Implementação técnica:

- Baseline global obrigatório em `openclaw.json`:
  - `tools.profile="messaging"` para agentes conversacionais;
  - `tools.deny` global com grupos sensíveis por padrão;
  - permissões específicas apenas por agente.
- Em `openclaw.json`, definir `tools.profile` e `allow/deny` por agente.
- Router sem tools de ação externa.
- Specialists com tools mínimas por responsabilidade.
- Deny de session-cross tools quando não necessário.
- Ordem de precedência (documentada e testada):
  - profile global/agent -> policy global -> policy por agent -> sandbox policy -> subagent policy.

Testes técnicos:

- invocação de tool fora da allowlist => bloqueio;
- sem regressão de tools via perfil global.
- snapshot do toolset efetivo por agente para detectar herança indevida.

## Epic 6 — Compliance de Camadas/Responsabilidades

### US-6.1 — Teste de dependência entre camadas
Implementação técnica:

- Criar suíte de arquitetura (lint estrutural ou teste estático) com regras:
  - `routing` não chama `actions` diretamente sem passar por especialista/plano;
  - especialista não chama outro especialista diretamente;
  - `governance` não executa envio de mensagem.

Testes técnicos:

- referência proibida entre módulos => falha de pipeline.

### US-6.2 — Review arquitetural obrigatório
Implementação técnica:

- Template de PR com checklist obrigatório:
  - fronteiras de camada preservadas;
  - contrato público atualizado;
  - RBAC validado;
  - auditoria em operações críticas.

Evidência de aprovação:

- aprovação explícita de arquiteto/tech lead no PR.

### US-6.3 — DoD arquitetural bloqueante
Implementação técnica:

- Merge gate:
  - testes funcionais passados;
  - testes de camada passados;
  - RBAC/auditoria validados;
  - review arquitetural aprovado.

Testes técnicos:

- qualquer gate reprovado => merge bloqueado.

## 4) Mudanças Recomendadas em `openclaw.json` (Blueprint)

Adicionar agentes dedicados (fase atual):

- `sales-ingress-agent`
- `intent-router-agent`
- `qualifier-agent`
- `objection-agent`
- `closing-agent`
- `handover-agent`
- `feedback-reviewer-agent`

Regras de tools:

- baseline global `default deny` para tools não explícitas;
- router: sem tools externas.
- qualifier: tools de qualificação/enrich.
- objection: tools de contexto/battlecards.
- closing: agenda/agendamento.
- handover: escalonamento.
- reviewer: leitura de métricas + proposta; sem apply final.

Bindings:

- WhatsApp de vendas -> `sales-ingress-agent`.
- Canal Discord `sales-bot-improvement` -> `feedback-reviewer-agent`.

Hooks (se usado para eventos internos):

- caminho preferencial: fila interna de domínio (sem hooks).
- fallback via hooks:
  - habilitar `hooks` com token dedicado;
  - restringir `allowedAgentIds` para `sales-ingress-agent`;
  - `allowRequestSessionKey=true` apenas com `allowedSessionKeyPrefixes=["hook:followup:"]`;
  - enviar sempre `deliver=false`;
  - proibir `channel/to` em eventos internos.

Validação de agent resolution (anti-fallback silencioso):

- adicionar gate de startup/CI que falha se `agentId` referenciado na TS não existir em `agents.list`.
- validar bindings obrigatórios para:
  - WhatsApp de vendas -> `sales-ingress-agent`
  - Discord de review -> `feedback-reviewer-agent`
- validar `hooks.allowedAgentIds` fechado, sem wildcard, quando fallback hooks estiver ativo.

## 5) Matriz US -> Artefatos

- Spec funcional: `docs/specs/crm-outbound-agent-v2/spec-2026-04-25-crm-outbound-agent-v2.md`
- User stories: `docs/specs/crm-outbound-agent-v2/US-2026-04-25-crm-outbound-agent-v2.md`
- Este documento técnico por US: `docs/specs/crm-outbound-agent-v2/TS-2026-04-25-crm-outbound-agent-v2.md`

## 6) Critério de Pronto Técnico

Todos os US só podem ser implementados quando:

- contrato público do US estiver definido;
- owner técnico por componente estiver definido;
- policy RBAC para operações do US estiver definida;
- testes unit/integration/architecture estiverem especificados;
- evidência de review arquitetural estiver prevista no PR.
