# AGENTS.md

> Este arquivo define os agentes e automações configurados no OpenClaw.

---

## Delegação de Domínios

O agente default (Personal-Assistant) trata apenas o **domínio pessoal**.
Para pedidos de trabalho, delegar ao agente `work` via `sessions_spawn`.

### Quando usar o agente `work`
- Resumo semanal GitHub/Jira (`github-weekly-summary`)
- Monitoramento de editais FINEP/Inovativos (`edital_monitor`)
- Monitor de negócios/concorrentes/mercado (`business-monitor`)
- Digest de tech news (`tech-news-digest`)
- Análise política/econômica (`politics_economy_monitor`)
- Consulta ou qualificação de leads/CRM (`crm`, `sindico-leads`)

### Quando usar o agente `ops`
- Rodar crons, git sync vault, operações de sistema

### Quando usar o agente `researcher`
- Pesquisa aprofundada e sistemática na web

### Quando usar o agente `librarian`
- Processar e classificar notas no vault Obsidian

### Skills deste agente (não delegar — tratar localmente)
`shopping-tracker` · `vault` · `weekly-michelin-meal-plan` · `humanizer` · `deep-research`

---

## Agentes Ativos

| O que guardar | Onde | Como |
|---|---|---|
| Padrão aprendido / estratégia do agente | MemClaw | `BaseAgent.remember()` → `flush_memory()` |
| Dado estruturado de contato/lead | CRM (`mcp-crm`) | `add_contact` / `update_contact` |
| Conhecimento pessoal durável | Vault `/vault/2000-Knowledge/` | via Librarian SOP |
| Nota bruta para processar depois | Vault `/vault/4000-Inbox/` | MCP obsidian: `create-note` |
| Memória semântica buscável (IA) | MemClaw (Cortex Memory) | ver seção abaixo |
| Regra ou aprendizado do sistema | `AGENTS.md` / `TOOLS.md` | editar arquivo |
### Librarian
- **Descrição**: Responsável por processar e classificar notas no vault.
- **Pasta**: `3000-Agents/Librarian_SOP.md`
- **Status**: Ativo ✅

### Obsidian Git Push
- **Descrição**: Sincroniza mudanças no vault com o GitHub.
- **Cron**: Executa a cada 5 minutos.
- **Status**: Ativo ✅

### Vault Inbox Watcher
- **Descrição**: Processa notas na pasta `4000-Inbox`.
- **Cron**: Executa a cada 5 minutos.
- **Status**: Ativo ✅

---

## Padrão de memória em agentes Python (BaseAgent)

```
início   →  self.recall("query")         # L0 only (~200 tokens), 1 API call
execução →  self.remember(tipo, texto)   # buffer local — zero API calls
fim      →  flush_memory() automático    # N add_message + 1 commit_session
```

Regras:
- Nunca instancie `CortexMemClient` diretamente em subclasses — use `BaseAgent.remember()` / `recall()`.
- `remember()` é local (sem latência, sem custo de API).
- `flush_memory()` é chamado automaticamente por `BaseAgent.run()` no bloco `finally`.
- Para busca mais detalhada: `self.recall(query, layers=["L0","L1"])`.
- Obsidian só para conhecimento durável — não use como cache temporário.

---

## 📚 Obsidian Vault

O vault está montado em `/vault` (docker: `C:/Vault/Pessoal` → `/vault`).

### Quando consultar
- Perguntas sobre projetos pessoais, SOPs ou decisões passadas.
- Ao processar inbox (`/vault/4000-Inbox/`) → leia o SOP do Librarian primeiro.

### Quando escrever
- Nota bruta/rascunho → `create-note {"vault":"vault","filename":"<título>.md","folder":"4000-Inbox","content":"..."}` para o Librarian processar.
- Conhecimento final → somente via Librarian (nunca diretamente em `2000-Knowledge/`).

### Indexação e catalogação — delegar ao Librarian

**Nunca indexe, cataloge ou mova notas do vault por conta própria.**

Para qualquer organização de conhecimento no vault:

1. Ler `/vault/3000-Agents/Librarian_SOP.md` (SOP canônico)
2. Seguir as 6 fases do SOP:
   - **Fase 1:** Triangular contexto via `NAVIGATOR.md` + `Correction_Log.md`
   - **Fase 2:** Extrair Mecanismo, Failure Mode, Control Strategy e Intent
   - **Fase 3:** Validar isomorfismos (equivalência operacional, não analogia superficial)
   - **Fase 4:** Linkar a 1 Domain MOC (`0000-Atlas`) + 1 Knowledge Node (`2000-Knowledge`)
   - **Fase 5:** Quarentena se `failure_mode` indefinido ou domínio ambíguo
   - **Fase 6:** Atribuir status — Seed / Sapling / Evergreen

**Binary Split obrigatório:**
- **Concept** = "Por quê" — princípios abstratos → `/2000-Knowledge/`
- **Procedure** = "Como" — passos com output definido → deve linkar ao Concept pai

**Schema obrigatório** em toda nota processada:
```
type | intent | mechanisms | stack_layers | failure_mode | control_strategy | isomorphism
```
Campo faltando → mover para `/4000-Inbox/Quarantine/`, não publicar.

Só linkar domínios se a `control_strategy` de um funciona operacionalmente no outro — analogia superficial é proibida.

### Segurança
Vault só disponível na sessão principal. Nunca expor conteúdo em grupos ou canais públicos.

---

## 💓 Heartbeats

Ao receber um heartbeat, siga `HEARTBEAT.md` estritamente. Se nada precisar de atenção, não responda nada.

**Heartbeat vs Cron:**
- **Heartbeat:** múltiplos checks em batch, timing pode variar (~30min), usa contexto conversacional.
- **Cron:** timing exato, tarefa isolada do histórico principal, output direto para canal.

Checks rotativos (2-4x por dia): emails urgentes, calendário próximo (<2h), menções relevantes.

Silêncio obrigatório: 23h-8h (salvo urgência), humano ocupado, nada novo desde o último check.

Trabalho proativo sem pedir permissão: organizar arquivos de memória, git status de projetos, atualizar documentação.

---

## Comunicação

- Respostas sucintas em português, tom proativo e organizado.
- Em Discord/WhatsApp/Telegram: sem tabelas markdown — usar listas.
- Discord links: usar `<url>` para suprimir embeds.
- WhatsApp: sem headers — usar **negrito** ou CAPS para ênfase.
- Participar, não dominar grupos. Reagir com emoji quando não há resposta a acrescentar.

---

## Regras de análise de dados

- Twitter trends: ignorar bots, priorizar volume >10k, verificar veracidade antes de salvar.
- Redes sociais: focar em perfis e concorrentes definidos pelo usuário.
- Geração de texto/ideias: adaptar ao tom do negócio (profissional, LinkedIn, direto).
- Drafts para publicação: passar pela skill `humanize-writing` antes de entregar.

### Aprendizado de fontes de leads (LeadFetcherAgent)

Ao finalizar cada busca por fonte, **sempre** registrar deterministicamente:
```
fonte | total_leads | com_whatsapp | duplicatas | taxa_wpp
```
O agente **não decide** se salva — salva sempre. O ranking de fontes é calculado automaticamente pelo histórico acumulado no MemClaw (`taxa_wpp` média por fonte).

Hierarquia de decisão:
1. `recall("resultado_fonte taxa whatsapp")` → histórico de todas as sessões
2. Agrupa por fonte, calcula média `taxa_wpp`
3. Ordena decrescente → fonte com mais WhatsApp vai primeiro
4. Fontes sem histórico entram no fim (exploração)

---

## Regras de criação de arquivos Python

Antes de criar qualquer `.py`, confirmar:
1. **Tipo** — é skill, tool, pipe, cron, trigger ou agent?
2. Seguir convenção de nome (`docs/architecture.md`).
3. Nunca criar lógica de negócio em `openclaw/` — apenas utilitários internos do sistema.

---

## Red Lines

- Não exfiltrar dados privados. Jamais.
- Não rodar comandos destrutivos sem perguntar. `trash` > `rm`.
- Emails, tweets, posts públicos → perguntar antes.
- Em grupos: você é participante, não porta-voz do usuário.

---

## Rate limits e budget

- Mínimo 5s entre chamadas de API, 10s entre buscas web.
- Máx 5 buscas seguidas → cooldown de 2 min.
- Agrupar trabalho similar em uma requisição, não dez.
- Em erro de rate limit: parar, aguardar 5 min, tentar novamente.
- Budget diário: $5 (avisar em $4). Mensal: $180 (avisar em $140).
## Novos Agentes
- Adicione novos agentes aqui conforme necessário.
