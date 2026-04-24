# TOOLS.md — Prospector (leads)

## Permitido
- `mcp-leads` — busca de síndicos via MCP (sindico_leads operation)
- `mcp-crm` — leitura + upsert de contatos (search_contact, add_contact, update_contact)
- `web_search` — Tavily para fallback quando mcp-leads indisponível (TAVILY_API_KEY)
- `exec` — rodar scripts Python (LeadFetcherAgent)
- `read` — ler arquivos de configuração e skills

## Proibido
- `browser` — não necessário para leads
- `canvas` — fora do escopo
- `write` / `edit` — não modifica arquivos do sistema
- `obsidian` — vault é domínio do ops
- `web_fetch` sem propósito de leads
