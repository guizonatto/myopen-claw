# TOOLS.md

> Este arquivo define as ferramentas e habilidades disponíveis no OpenClaw.

---

## Ferramentas Ativas

### Obsidian MCP
- **Descrição**: Permite interagir com o vault do Obsidian.
- **Habilidades**: Ler, criar, mover e editar notas.
- **Status**: Ativo ✅

### Git MCP
- **Descrição**: Permite sincronizar mudanças com o GitHub.
- **Habilidades**: Fazer `add`, `commit`, `push` e `pull`.
- **Status**: Ativo ✅

### obsidian MCP (navegação + leitura/escrita + busca)

MCP `obsidian` registrado em `openclaw.json` via `npx -y obsidian-mcp@1.0.6 /vault` (ou `obsidian-mcp@${OBSIDIAN_MCP_VERSION}` em runtime).
Não requer Obsidian app rodando — acessa arquivos diretamente.
Use sempre `kebab-case`, com `vault` explícito e caminhos relativos.

| Operação | Tool |
|---|---|
| Descobrir vault | `list-available-vaults` |
| Buscar notas por nome/conteúdo | `search-vault {"vault":"vault","query":"...","searchType":"filename|content|both"}` |
| Ler nota | `read-note {"vault":"vault","filename":"Note.md","folder":"Folder"}` |
| Criar/escrever nota | `create-note` / `edit-note` |
| Gerenciar tags | `add-tags` / `remove-tags` |
| Mover nota | `move-note` |

### Migração legado (somente referência)

| Antigo | Atual |
|---|---|
| `list_notes` | `search-vault` (listar: `searchType:"filename"` + `query:".md"`) |
| `read_note` | `read-note` |
| `create_note` | `create-note` |
| `edit_note` | `edit-note` |
| `move_note` | `move-note` |
| `search_notes` | `search-vault` |
| `add_tag` | `add-tags` |
| `remove_tag` | `remove-tags` |

### Estrutura do vault

| Pasta | Conteúdo |
|---|---|
| `/vault/4000-Inbox/` | Notas novas a processar (monitorado a cada 5min) |
| `/vault/2000-Knowledge/` | Base de conhecimento indexada no RAG (reindexada às 3h) |
| `/vault/3000-Agents/Librarian_SOP.md` | SOP do agente Librarian |
### Librarian
- **Descrição**: Processa e classifica notas automaticamente.
- **Habilidades**: Aplicar `Librarian_SOP` e mover notas.
- **Status**: Ativo ✅

---

## Novas Ferramentas
- Adicione novas ferramentas aqui conforme necessário.