# TOOLS.md — Cheat sheet do ambiente OpenClaw

Documenta o que está disponível neste setup específico.
Atualizar sempre que uma nova integração for adicionada.

---

## Obsidian Vault

Vault montado em `/vault` (host: `C:\Vault\Pessoal`). Acesso via obsidian MCP.

> Todos os CLIs `obsidian-cli` disponíveis são REST API clients (requerem Obsidian app + plugin). Use obsidian MCP para acesso direto.

### obsidian MCP (navegação + leitura/escrita + busca)

MCP `obsidian` registrado em `openclaw.json` via `npx obsidian-mcp /vault`.
Não requer Obsidian app rodando — acessa arquivos diretamente.

| Operação | Tool |
|---|---|
| Listar notas | `list_notes` |
| Ler nota | `read_note "Folder/Note"` |
| Criar/escrever nota | `create_note` / `edit_note` |
| Buscar por conteúdo | `search_notes "query"` |
| Gerenciar tags | `add_tag` / `remove_tag` |
| Mover nota | `move_note` |

### Estrutura do vault

| Pasta | Conteúdo |
|---|---|
| `/vault/4000-Inbox/` | Notas novas a processar (monitorado a cada 5min) |
| `/vault/2000-Knowledge/` | Base de conhecimento indexada no RAG (reindexada às 3h) |
| `/vault/3000-Agents/Librarian_SOP.md` | SOP do agente Librarian |

---

## MCPs (Model Context Protocol)

Acessados via `docker exec` STDIO pelo gateway. Registrados em `openclaw.json`.

## Tools nativas do Gateway

| Tool | O que faz |
|---|---|
| `web_search` | Busca web via provider configurado (default: `duckduckgo`, pode ser `tavily`) |
| `web_fetch` | Fetch simples de uma URL (sem browser) |
| `browser` | Navegador automatizado (JS-heavy, logins, cliques) |

> **Nomes de tools:** o nome que aparece aqui é o **nome exato** que o agente deve chamar (ex: `add_contact`, `sindico_leads`).

| MCP (id no `openclaw.json`) | Container | Porta HTTP | O que faz |
|---|---|---|---|
| `mcp-crm` | `mcp-crm` | 8001 | CRM de contatos: add, search, update, follow-up |
| `mcp-leads` | `mcp-leads` | 8002 | Prospecção de leads (scraping) + upsert no CRM |
| `mcp-trends` | `mcp-trends` | 8000 | Trends de mercado (armazenamento/consulta) |
| `mcp-shopping` | `mcp-shopping-tracker` | 8003 | Rastreamento de listas de compras |
| `obsidian` | `openclaw-gateway` (npx) | — | Vault Obsidian: read, write, search, tags |

> Nota: o onboarding do OpenClaw também pode registrar aliases (`crm`, `shopping`, `trends`). Eles apontam para os mesmos containers, mas **prefira os ids `mcp-*`** para evitar ambiguidade.

### Operações disponíveis — mcp-crm

| Tool | Campos obrigatórios | Campos opcionais |
|---|---|---|
| `add_contact` | `nome` + (`email` \| `whatsapp` \| `telefone`) | `email`, `whatsapp`, `telefone`, `cnpj`, `cnaes` |
| `search_contact` | `query` | — |
| `update_contact` | `contact_id` | `pipeline_status`, `stage`, `icp_type`, `nota`, `whatsapp`, `empresa`, `cargo`, `tipo` |
| `list_contacts_to_follow_up` | — | `hours_since_last_contact` (default 24), `limit` (default 10) |

### Operações disponíveis — mcp-leads

| Tool | Quando usar | Params |
|---|---|---|
| `sindico_leads` | Buscar e registrar leads de síndicos profissionais (sem PII no retorno) | `max_results` (default 20), `city` (default "São Paulo"), `query` (opcional) |
| `execute_lead_skill` | Wrapper genérico (use apenas se precisar chamar outra `operation`) | `operation` + `params` |

### Operações disponíveis — mcp-trends

| Tool | O que faz | Params |
|---|---|---|
| `execute_trend_skill` | Wrapper do MCP trends | `operation` + `params` |

Operações aceitas no `operation` (via `execute_trend_skill`):
- `replace_trends` (`params.trends`: lista de strings)
- `list_trends` (`params.limit`: int, default 100)
- `ping` (`params`: `{}`)

### Operações disponíveis — mcp-shopping

| Tool | O que faz | Params |
|---|---|---|
| `registrar_compra` | Registra compras (e/ou wishlist) | `compras`: lista de itens |
| `listar_wishlist` | Lista wishlist | — |

---

## Verificar registro no `openclaw.json`

**Persistido (em runtime):** `/root/.openclaw/openclaw.json` dentro do container `openclaw-gateway`.

Comandos úteis (PowerShell):
- `docker exec -i openclaw-gateway sh -lc "node /app/dist/index.js mcp list"`
- `docker exec -i openclaw-gateway sh -lc "python3 - <<'PY'\nimport json\nfrom pathlib import Path\ncfg=json.loads(Path('/root/.openclaw/openclaw.json').read_text('utf-8'))\nprint(sorted(cfg.get('mcp',{}).get('servers',{}).keys()))\nPY"`

---

## Canais de comunicação

| Canal | Container / Serviço | Detalhes |
|---|---|---|
| **Telegram** | Bot via API | Token: `TELEGRAM_BOT_TOKEN` |
| **WhatsApp** | Evolution API (`openclaw-evolution-api`, porta 8080) | Instância: `EVOLUTION_INSTANCE` |
| **Discord** | Bot via API | Token: `DISCORD_BOT_TOKEN`, Guild: `DISCORD_GUILD_ID` |

### Evolution API — Referência completa

Base: `{EVOLUTION_URL}` | Auth: `apikey: {EVOLUTION_API_KEY}` | Instância: `{EVOLUTION_INSTANCE}`

Todas as rotas seguem o padrão: `POST|GET|PUT|DELETE {EVOLUTION_URL}/{endpoint}/{EVOLUTION_INSTANCE}`

#### Outbound — Envio de mensagens

| Método | Endpoint | O que faz |
|---|---|---|
| POST | `/message/sendText/{instance}` | Texto simples com simulação de digitação |
| POST | `/message/sendMedia/{instance}` | Imagem, vídeo ou documento |
| POST | `/message/sendAudio/{instance}` | Áudio (PTT / nota de voz) |
| POST | `/message/sendSticker/{instance}` | Sticker |
| POST | `/message/sendLocation/{instance}` | Localização (lat/lng) |
| POST | `/message/sendContact/{instance}` | Contato vCard |
| POST | `/message/sendReaction/{instance}` | Reação em emoji a uma mensagem |
| POST | `/message/sendPoll/{instance}` | Enquete |
| POST | `/message/sendList/{instance}` | Lista com opções clicáveis |
| POST | `/message/sendButtons/{instance}` | Mensagem com botões |
| POST | `/message/sendStatus/{instance}` | Story / Status WhatsApp |

**Exemplo — texto com digitação humana:**
```json
POST /message/sendText/{instance}
{
  "number": "5511999990000",
  "text": "Oi João!",
  "options": { "presence": "composing", "delay": 2400 }
}
```

**Fórmula do delay:** `len(mensagem) * 40ms`, mín 1500ms, máx 8000ms

#### Inbound — Webhook (receber mensagens)

| Método | Endpoint | O que faz |
|---|---|---|
| POST | `/webhook/{instance}` | Configura URL de webhook para receber eventos |
| GET | `/webhook/{instance}` | Consulta configuração atual do webhook |

**Eventos recebidos via webhook:**
- `messages.upsert` — nova mensagem recebida
- `messages.update` — mensagem atualizada (lida, entregue, deletada)
- `connection.update` — mudança de status da instância
- `qrcode.updated` — novo QR code gerado

#### Chat — Gerenciamento de conversas

| Método | Endpoint | O que faz |
|---|---|---|
| GET | `/chat/findChats/{instance}` | Lista todas as conversas |
| GET | `/chat/findMessages/{instance}` | Busca mensagens de uma conversa |
| GET | `/chat/findContacts/{instance}` | Lista todos os contatos |
| POST | `/chat/checkIsWhatsapp/{instance}` | Verifica se número tem WhatsApp |
| POST | `/chat/markRead/{instance}` | Marca mensagem como lida |
| POST | `/chat/sendPresence/{instance}` | Envia status "digitando..." manualmente |
| PUT | `/chat/updateMessage/{instance}` | Edita uma mensagem enviada |
| DELETE | `/chat/deleteMessage/{instance}` | Apaga mensagem para todos |
| GET | `/chat/profilePictureUrl/{instance}` | Foto de perfil de um número |
| POST | `/chat/archiveChat/{instance}` | Arquiva conversa |
| PUT | `/chat/blockStatus/{instance}` | Bloqueia/desbloqueia contato |

#### Grupos

| Método | Endpoint | O que faz |
|---|---|---|
| POST | `/group/create/{instance}` | Cria grupo |
| GET | `/group/fetchAllGroups/{instance}` | Lista todos os grupos |
| GET | `/group/findGroupInfos/{instance}` | Detalhes de um grupo |
| GET | `/group/participants/{instance}` | Lista membros |
| PUT | `/group/updateParticipant/{instance}` | Adiciona/remove/promove membros |
| PUT | `/group/updateGroupPicture/{instance}` | Atualiza foto do grupo |
| PUT | `/group/updateGroupSubject/{instance}` | Atualiza nome do grupo |
| PUT | `/group/updateGroupDescription/{instance}` | Atualiza descrição |
| GET | `/group/inviteCode/{instance}` | Obtém link de convite |
| DELETE | `/group/leaveGroup/{instance}` | Sai do grupo |

#### Instância

| Método | Endpoint | O que faz |
|---|---|---|
| GET | `/instance/connectionState/{instance}` | Status da conexão |
| POST | `/instance/connect/{instance}` | Gera QR code para conectar |
| POST | `/instance/restart/{instance}` | Reinicia instância |
| POST | `/instance/logout/{instance}` | Desconecta instância |
| PUT | `/instance/presence/{instance}` | Define presença (online/offline) |
| PUT | `/settings/set/{instance}` | Configura settings da instância (dmPolicy, etc) |

**Configuração obrigatória para bot de vendas (receber msgs de desconhecidos):**
```json
PUT /settings/set/{instance}
{ "dmPolicy": "public" }
```
> Sem isso, o bot só recebe mensagens de contatos salvos na agenda.

#### Perfil

| Método | Endpoint | O que faz |
|---|---|---|
| GET | `/profile/{instance}` | Dados do perfil |
| PUT | `/profile/name/{instance}` | Atualiza nome |
| PUT | `/profile/status/{instance}` | Atualiza status/recado |
| PUT | `/profile/picture/{instance}` | Atualiza foto |
| GET | `/profile/privacy/{instance}` | Configurações de privacidade |

---

## Infraestrutura

| Serviço | Container | Porta | Função |
|---|---|---|---|
| PostgreSQL + pgvector | `postgres` | 5433 | Banco de dados principal |
| Redis | `openclaw-redis` | — | Cache (usado pela Evolution API) |
| OpenClaw Gateway | `openclaw-gateway` | 18789 | Roteador principal de canais e agentes |
| Evolution API | `openclaw-evolution-api` | 8080 | Bridge WhatsApp |
| Auto-updater | `openclaw-auto-updater` | — | Git pull + migrations + skills sync às 3h |

---

## Variáveis de ambiente (.env)

| Variável | Usada por |
|---|---|
| `DATABASE_URL` | Todos os MCPs |
| `MCP_API_KEY` | Autenticação dos MCPs |
| `TELEGRAM_BOT_TOKEN` | Gateway — canal Telegram |
| `TELEGRAM_USER_ID` | Gateway — allowlist Telegram |
| `TELEGRAM_CHANNEL_ID` | Crons — canal de envio |
| `DISCORD_BOT_TOKEN` | Gateway — canal Discord |
| `DISCORD_GUILD_ID` | Skill usell-sales-workflow — canais de aprendizado |
| `EVOLUTION_URL` | Skill usell-sales-workflow — envio WhatsApp |
| `EVOLUTION_INSTANCE` | Skill usell-sales-workflow — instância conectada |
| `EVOLUTION_API_KEY` | Skill usell-sales-workflow — autenticação |
| `ADMIN_PASSWORD` | Gateway — senha de administrador |
| `GATEWAY_BIND` | Gateway — endereço de bind |
| `SKILLS_GIT_REPO` | Gateway — repositório externo de skills |
| `AUTO_INSTALL_SKILLS` | Gateway — skills instaladas no bootstrap |
| `ENABLE_SANDBOX` | Gateway — modo sandbox |
| `ENABLE_WHATSAPP` | Gateway — habilita canal WhatsApp Baileys |
| `GLOBAL_WEB_SEARCH_PROVIDER` | Gateway — provedor global de busca web (default recomendado: `duckduckgo`; fallback para `duckduckgo` se o provider exigir key e ela estiver vazia) |
| `WEB_SEARCH_PROVIDER` | Gateway — compat/legado; usado apenas se `GLOBAL_WEB_SEARCH_PROVIDER` estiver vazio ou `duckduckgo` |
| `TAVILY_API_KEY` | Skills de maior valor — Tavily para pesquisa focada |
| `BRAVE_API_KEY` | Skills específicas — Brave Search overflow opcional |
| `BRAVE_API_KEYS` | Skills específicas — rotação de chaves Brave |
| `FIRECRAWL_API_KEY` | Gateway — scraping via Firecrawl |
| `ZAI_API_KEY` | Gateway — provider z.ai |
| `OPENAI_CODEX` | Gateway — provider OpenAI Codex |

---

## Política de Search/Browser por skill

Ordem de custo/uso recomendada neste setup:

1. `web_fetch` para URLs conhecidas e fontes fixas
2. `web_search` global com `duckduckgo`
3. `Tavily` apenas para pesquisa focada de maior valor
4. `browser` apenas para sites JS-heavy, login-gated ou fluxos com clique

### Mapeamento atual

| Skill | Caminho padrão | Uso premium/exceção |
|---|---|---|
| `business-monitor` | `web_fetch` nas fontes fixas | `web_search` só se a fonte mudar |
| `edital_monitor` | `web_fetch` nas páginas institucionais | `web_search` domain-scoped; `browser` só se a listagem for JS |
| `politics_economy_monitor` | `web_fetch` nas seções/fontes fixas | `web_search` seletivo; Tavily só em picos temáticos |
| `curadoria-temas-diarios` | `web_search` (`duckduckgo`) + `web_fetch` | Tavily apenas para IA, tecnologia, startups/negócios e ciência |
| `daily-content-creator` | Tavily + `web_fetch` | `browser` apenas para LinkedIn ou páginas JS/login |
| `tech-news-digest` | RSS/GitHub/Reddit + Tavily no `fetch-web.py` | Brave apenas como overflow |
| `fetch-trending-topics` / `x-trending` | `browser` | Não gastar Tavily |
| `trends` | `web_fetch` em `trends24.in` | `browser` só se a página quebrar |
| `reddit-digest` / `reddit_digest` | Reddit JSON/API + `web_fetch` opcional para links externos | Sem busca web por padrão |
| `github-weekly-summary` | APIs GitHub/Jira/Notion/Discord | Sem `web_search`/`browser` |
| `sindico-leads` | `web_search` (`duckduckgo`) + `web_fetch` | Tavily só para shortlist; `browser` para LinkedIn/Instagram/diretórios JS |

---

## Regra

Toda nova integração externa deve ser documentada aqui.
Toda nova variável de ambiente deve ser adicionada ao `.env.example`.
