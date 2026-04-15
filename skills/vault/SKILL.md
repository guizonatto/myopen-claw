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

| Pasta | Conteúdo |
|---|---|
| `/vault/4000-Inbox/` | Notas novas a processar (Librarian monitora a cada 5min) |
| `/vault/2000-Knowledge/` | Base de conhecimento (reindexada no RAG às 3h) |
| `/vault/3000-Agents/Librarian_SOP.md` | SOP do agente Librarian |

## Fluxo do inbox
1. Nova nota cai em `4000-Inbox/`
2. `read_note "3000-Agents/Librarian_SOP"`
3. Processar e `move_note` para pasta correta
