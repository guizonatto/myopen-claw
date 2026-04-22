---
name: vault
description: "Acesso ao vault Obsidian via MCP obsidian."
metadata:
  openclaw:
    model: usage-router/groq/openai/gpt-oss-20b
---

# Skill: vault

Acesso ao vault Obsidian em `/vault` via MCP **obsidian** (`obsidian-mcp`).
Não requer Obsidian app rodando — opera diretamente nos arquivos.

## Operações disponíveis

### Buscar notas por conteúdo
```
search_notes "query"
```

### Listar notas
```
list_notes
list_notes "4000-Inbox"
```

### Ler nota
```
read_note "2000-Knowledge/Minha Nota"
```

### Criar nota
```
create_note "4000-Inbox/Nova Nota" <conteúdo>
```

### Editar nota
```
edit_note "2000-Knowledge/Minha Nota" <novo conteúdo>
```

### Mover nota
```
move_note "4000-Inbox/nota" "2000-Knowledge/nota"
```

### Gerenciar tags
```
add_tag "2000-Knowledge/nota" "tag"
remove_tag "2000-Knowledge/nota" "tag"
```

## Estrutura do vault

| Pasta / Arquivo | Conteúdo |
|---|---|
| `/vault/4000-Inbox/` | Notas novas a processar (Librarian monitora a cada 5min) |
| `/vault/4000-Inbox/Quarantine/` | Notas sem `failure_mode` ou domínio claro |
| `/vault/2000-Knowledge/` | Base de conhecimento (reindexada no RAG às 3h) |
| `/vault/0000-Atlas/` | Maps of Content (MOCs) por domínio |
| `/vault/3000-Agents/Librarian_SOP.md` | **Fonte única do Librarian** — role, binary split, fases de extração, qualidade, manutenção |
| `/vault/NAVIGATOR.md` | Mapa do vault — domínios, foco atual, referência ao Librarian_SOP |
| `/vault/9000-System/Schema_Definitions.md` | **Fonte canônica de schema** — valores válidos para type, intent, mechanisms, failure_mode, control_strategy, isomorphism, status. Novos valores só com `[PROPOSED_NEW_VALUE]` |
| `/vault/9000-System/Templates/Smartable_Note.md` | Template frontmatter + seções para novas notas |

## Hierarquia de documentos do agente

Ao processar qualquer nota, o agente carrega nesta ordem:

1. `3000-Agents/Librarian_SOP.md` — como operar (role + fases de execução)
2. `9000-System/Schema_Definitions.md` — valores válidos de schema
3. `NAVIGATOR.md` — domínios disponíveis para linking
4. `9000-System/Templates/Smartable_Note.md` — só ao criar nota nova

> Não existem mais `Reasoning_Protocol.md` nem `System_Instructions.md`.
> Tudo foi consolidado em `Librarian_SOP.md` + `Schema_Definitions.md`.

## Fluxo do inbox

1. Nova nota cai em `4000-Inbox/`
2. `list_notes "4000-Inbox"` — se vazio, parar
3. `read_note "3000-Agents/Librarian_SOP"` + `read_note "9000-System/Schema_Definitions"`
4. Aplicar binary split (Concept vs Procedure)
5. Extrair `failure_mode`, `control_strategy`, `mechanisms`, `isomorphism`
6. Validar schema — campos obrigatórios todos presentes?
   - Não → `move_note` para `4000-Inbox/Quarantine/`
7. `move_note` para pasta correta em `2000-Knowledge/`
