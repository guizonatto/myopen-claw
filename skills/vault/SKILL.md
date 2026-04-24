---
name: vault
description: "Acesso ao vault Obsidian"
metadata:
  openclaw:
    model: google/gemini-2.5-flash
---

# Skill: vault

Acesso ao vault Obsidian em `/vault`
Não requer Obsidian app rodando — opera diretamente nos arquivos.

## Operações disponíveis

### Descobrir vault disponível
```
list-available-vaults
```

### Buscar notas por conteúdo/nome (equivalente a listar)
```
search-vault {"vault":"vault","query":"project","searchType":"content"}
search-vault {"vault":"vault","query":".md","path":"4000-Inbox","searchType":"filename"}
```

### Ler nota
```
read-note {"vault":"vault","filename":"Minha Nota.md","folder":"2000-Knowledge"}
```

### Criar nota
```
create-note {"vault":"vault","filename":"Nova Nota.md","folder":"4000-Inbox","content":"<conteúdo>"}
```

### Editar nota
```
edit-note {"vault":"vault","filename":"Minha Nota.md","folder":"2000-Knowledge","operation":"replace","content":"<novo conteúdo>"}
```

### Mover nota
```
move-note {"vault":"vault","source":"4000-Inbox/nota.md","destination":"2000-Knowledge/nota.md"}
```

### Gerenciar tags
```
add-tags {"vault":"vault","files":["2000-Knowledge/nota.md"],"tags":["tag"]}
remove-tags {"vault":"vault","files":["2000-Knowledge/nota.md"],"tags":["tag"]}
```

### Migração legado (somente referência)

| Antigo | Atual |
|---|---|
| `list_notes` | `search-vault` (com `searchType:"filename"`) |
| `read_note` | `read-note` |
| `create_note` | `create-note` |
| `edit_note` | `edit-note` |
| `move_note` | `move-note` |
| `search_notes` | `search-vault` |
| `add_tag` | `add-tags` |
| `remove_tag` | `remove-tags` |

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
2. `search-vault {"vault":"vault","query":".md","path":"4000-Inbox","searchType":"filename"}` — se vazio, parar
3. `read-note {"vault":"vault","filename":"Librarian_SOP.md","folder":"3000-Agents"}` + `read-note {"vault":"vault","filename":"Schema_Definitions.md","folder":"9000-System"}`
4. Aplicar binary split (Concept vs Procedure)
5. Extrair `failure_mode`, `control_strategy`, `mechanisms`, `isomorphism`
6. Validar schema — campos obrigatórios todos presentes?
   - Não → `move-note` para `4000-Inbox/Quarantine/<arquivo>.md`
7. `move-note` para pasta correta em `2000-Knowledge/`
