# User Stories — CRM Outbound Agent v2

Date: 2026-04-25  
Escopo: `single-tenant (Zind)`  
Formato: `Epics + User Stories + Acceptance Criteria (Given/When/Then)`

## Epic 1 — Ingestion/Buffer Anti-Tiroteio

### US-1.1
Como operador de vendas, quero que mensagens sequenciais do lead sejam agrupadas antes do roteamento para evitar respostas duplicadas.

Acceptance Criteria:

- Given um lead envia 3 mensagens curtas em sequência, When o buffer processa os eventos, Then apenas 1 payload consolidado é enviado ao roteador.
- Given o buffer consolidou mensagens, When o roteador é acionado, Then existe no output `grouped_count > 1` e `flush_reason` registrado.

### US-1.2
Como sistema, quero fechar o buffer por completude semântica para responder com contexto correto sem depender de tempo fixo.

Acceptance Criteria:

- Given o lead envia uma pergunta completa, When a mensagem entra no buffer, Then ocorre flush imediato por completude.
- Given não há completude detectada, When guardrails são atingidos (`max_hold_ms`, `max_msgs` ou `max_chars`), Then ocorre flush técnico com motivo explícito.

### US-1.3
Como tech lead, quero garantir uma execução por lead para impedir concorrência assíncrona.

Acceptance Criteria:

- Given dois eventos chegam quase no mesmo instante para o mesmo lead, When o lock de execução é aplicado, Then só uma execução ativa permanece.

Definition of Done (Epic 1):

- Sem respostas duplicadas por rajada;
- rastreabilidade de `flush_reason` em logs.

## Epic 2 — Multimodal + Humanização

### US-2.1
Como lead, quando envio áudio, quero que o sistema compreenda meu conteúdo para manter a conversa fluida.

Acceptance Criteria:

- Given inbound com mídia de áudio, When o pipeline processa a entrada, Then `transcribe_incoming_audio` é executado e retorna texto com confiança.
- Given transcrição concluída, When o contexto é montado, Then `is_audio=true` e `transcript_text` estão presentes.

### US-2.2
Como gestor comercial, quero mensagens curtas no WhatsApp para manter tom humano.

Acceptance Criteria:

- Given resposta com até 220 caracteres, When o draft é finalizado, Then ela não é quebrada.
- Given resposta com mais de 220 caracteres, When o draft é finalizado, Then ela é quebrada em 2-3 mensagens.
- Given um bloco com múltiplas mensagens, When o CTA é gerado, Then o CTA aparece somente no último chunk.

### US-2.3
Como lead, quero perceber timing humano ao receber resposta.

Acceptance Criteria:

- Given houve inbound antes do envio, When o outbound ocorre, Then read-delay é aplicado antes da digitação.
- Given envio com múltiplos chunks, When cada chunk é enviado, Then typing-delay é aplicado por chunk.

Definition of Done (Epic 2):

- Sem textão único acima de 220;
- logs com timing de leitura/digitação.

## Epic 3 — Follow-up Proativo

### US-3.1
Como operação de outbound, quero seguir leads silenciosos automaticamente para recuperar oportunidades.

Acceptance Criteria:

- Given lead sem resposta por 24h, When worker de dormência roda, Then evento `timeout_24h` é gerado.
- Given lead sem resposta por 48h, When worker roda novamente, Then evento `timeout_48h` é gerado.
- Given lead sem resposta por 72h, When worker roda novamente, Then evento `timeout_72h` é gerado.

### US-3.2
Como gestor, quero limitar insistência automática para evitar desgaste.

Acceptance Criteria:

- Given chegou ao timeout de 72h sem resposta, When avaliação proativa finaliza, Then automação é pausada e revisão humana é aberta.

Definition of Done (Epic 3):

- Sequência 24/48/72 operacional;
- pausa obrigatória após 72h.

## Epic 4 — Feedback Reviewer + Aprovação Humana

### US-4.1
Como reviewer de vendas, quero revisar resultados do batch em thread no Discord para discutir ajustes com o time.

Acceptance Criteria:

- Given batch finalizado, When sessão de review inicia, Then é criada thread em `sales-bot-improvement`.
- Given feedback textual do humano, When registrado, Then feedback fica vinculado à sessão de review.

### US-4.2
Como sales manager, quero aprovar ou rejeitar mudanças de estratégia antes de produção.

Acceptance Criteria:

- Given proposta gerada pelo reviewer, When não houver aprovação, Then a estratégia ativa não é alterada.
- Given proposta aprovada, When próximo batch inicia, Then estratégias aprovadas passam a valer.

### US-4.3
Como operação, quero rastrear o ciclo de proposta para auditoria.

Acceptance Criteria:

- Given uma proposta, When ela muda de status, Then transições seguem `draft_review -> pending_approval -> approved/rejected`.

Definition of Done (Epic 4):

- Nenhuma alteração de estratégia sem aprovação humana;
- histórico de proposta completo por batch.

## Epic 5 — RBAC e Auditoria

### US-5.1
Como platform admin, quero permissões por role para impedir operação fora de responsabilidade.

Acceptance Criteria:

- Given usuário sem permissão para operação crítica, When tenta executar a ação, Then recebe `denied` e evento auditado.

### US-5.2
Como auditor, quero trilha de decisão nas ações críticas.

Acceptance Criteria:

- Given `approve_first_touch`, `mark_no_interest` ou `approve/reject_strategy_updates`, When executadas, Then logs incluem `who`, `role`, `reason`, `timestamp`.

### US-5.3
Como arquiteto, quero tool allowlist por agente para reduzir alucinação operacional.

Acceptance Criteria:

- Given agente tenta invocar tool fora da allowlist, When chamada é feita, Then execução é bloqueada.

Definition of Done (Epic 5):

- `default deny` ativo;
- auditoria obrigatória para mutações críticas.

## Epic 6 — Compliance de Camadas/Responsabilidades

### US-6.1
Como equipe de engenharia, quero detectar violações de dependência entre camadas antes do merge.

Acceptance Criteria:

- Given chamada proibida entre camadas, When testes arquiteturais rodam, Then pipeline falha.

### US-6.2
Como tech lead, quero review final focado em responsabilidade de módulos.

Acceptance Criteria:

- Given PR pronto para merge, When review final ocorre, Then checklist de camadas/responsabilidades é preenchido e aprovado.

### US-6.3
Como negócio, quero que o DoD inclua integridade arquitetural para evitar dívida técnica.

Acceptance Criteria:

- Given feature marcada como concluída, When gates de arquitetura/RBAC não passam, Then merge permanece bloqueado.

Definition of Done (Epic 6):

- Sem violações de camadas;
- aprovação arquitetural explícita no PR.

## Nota de Compatibilidade de Documentação

- Documento de spec canônico desta fase: `docs/specs/crm-outbound-agent-v2/spec-2026-04-25-crm-outbound-agent-v2.md`.
- Documento técnico por US: `docs/specs/crm-outbound-agent-v2/TS-2026-04-25-crm-outbound-agent-v2.md`.
- Documento legado v1: `docs/specs/2026-04-23-mcp-crm-enriquecimento-outreach-v1.md` (histórico).
