# MEMORY.md — Memória no OpenClaw (Vault + CRM + MemClaw)

## Princípios (fonte canônica vs. índice)

- **Vault (Obsidian)** é a **fonte canônica** de conhecimento pessoal (notas, SOPs, decisões duráveis).
- **CRM (`mcp-crm`)** é a **fonte canônica** de dados estruturados de contatos/leads e suas notas/histórico.
- **MemClaw (plugin `memclaw` + `cortex-mem-service`)** é a **memória semântica / índice (RAG)**: serve para recuperar contexto entre sessões.

> Não use `obsidian-cli` (é um REST client e exige Obsidian app + plugin).
> O antigo `mcp-memories` foi descontinuado neste setup; memória de longo prazo agora é MemClaw.

## Mapa de memória — qual camada usar

| O que guardar | Onde | Como |
|---|---|---|
| Contato/lead (campos estruturados) | `mcp-crm` | `add_contact`, `update_contact` |
| Nota/histórico de um contato (CRM) | `mcp-crm` | `update_contact` com `nota` (append com timestamp) |
| Conhecimento pessoal durável | Vault `/vault/2000-Knowledge/` | MCP `obsidian`: `create_note` / `edit_note` / `move_note` |
| Nota bruta para processar depois | Vault `/vault/4000-Inbox/` | MCP `obsidian`: `create_note` |
| Memória semântica buscável (IA) | MemClaw (Cortex Memory) | `cortex_search`, `cortex_add_memory`, `cortex_commit_session` |
| Regras/aprendizados do sistema | `configs/AGENTS.md` / `configs/TOOLS.md` | editar arquivo |

---

## MemClaw (Cortex Memory) — como usar

### Recuperar (buscar contexto)

- Use `cortex_search` primeiro (padrão `return_layers=["L0"]` é o mais barato em tokens).
- Se precisar de mais detalhe, use `cortex_recall` (L0+L2) ou `cortex_search` com `return_layers=["L0","L1"]`.
- Quando a busca não resolver, navegue com `cortex_ls` + `cortex_get_abstract`/`cortex_get_overview`/`cortex_get_content`.

### Armazenar (explícito)

- Use `cortex_add_memory` para registrar fatos/decisões/observações que precisam ser recuperáveis depois.
  - Prefira um `session_id` **estável** para automações (ex: `agent-lead_fetcher`).
  - Use `metadata` para tags/categoria/origem quando fizer sentido.
- Use `cortex_commit_session` em checkpoints naturais (fim de um tópico, após uma decisão importante) para disparar extração/consolidação.

### Onde fica (infra)

- Serviço: `${CORTEX_MEM_URL:-http://cortex-mem:8085}` (porta 8085)
- Persistência (Docker): volumes `qdrant-data` + `cortex-mem-data`

---

## Vault (Obsidian)

- Vault em `/vault` — é um repositório git clonado de `https://github.com/guizonatto/obsidian`.
- **Git sync automático**: pull a cada 1h (`obsidian-git-pull`), push a cada 5min quando há mudanças (`obsidian-git-push`).
- Acesso via MCP `obsidian` (configurado como `npx -y obsidian-mcp /vault`) para operações de conteúdo.
- Para operações git diretas (ex: forçar pull/push fora do cron), use shell: `git -C /vault ...`.
- Operações comuns: `list_notes`, `read_note`, `create_note`, `edit_note`, `move_note`, `search_notes`, `add_tag`, `remove_tag`.

> **Local-first**: o vault é lido/escrito diretamente nos arquivos em `/vault`. O MCP obsidian acessa o filesystem local — não requer app Obsidian rodando.

---

## CRM (`mcp-crm`)

- Use `add_contact` / `search_contact` / `update_contact` / `list_contacts_to_follow_up`.
- Para registrar histórico/observações do contato, use `update_contact` com `nota` (o MCP faz append com timestamp).
