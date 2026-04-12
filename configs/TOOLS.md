# TOOLS.md — Cheat sheet do ambiente OpenClaw

Documenta o que está disponível neste setup específico.
Atualizar sempre que uma nova integração for adicionada.

---

## MCPs (Model Context Protocol)

Acessados via `docker exec` STDIO pelo gateway. Registrados em `openclaw.json`.

| MCP | Container | Porta HTTP | O que faz |
|---|---|---|---|
| `mcp-crm` | `mcp-crm` | 8001 | CRM de contatos: add, search, update, follow-up |
| `mcp-memories` | `mcp-memories` | 8002 | Memórias e relacionamentos pessoais |
| `mcp-trends` | `mcp-trends` | 8000 | Trends de mercado (Twitter, LinkedIn, Google) |
| `mcp-shopping-tracker` | `mcp-shopping-tracker` | 8003 | Rastreamento de listas de compras |

### Operações disponíveis — mcp-crm

| Tool | Campos obrigatórios | Campos opcionais |
|---|---|---|
| `add_contact` | `nome`, `email` | `whatsapp`, `cnpj`, `cnaes` |
| `search_contact` | `query` | — |
| `update_contact` | `contact_id` | `pipeline_status`, `stage`, `icp_type`, `nota`, `whatsapp`, `empresa`, `cargo`, `tipo` |
| `list_contacts_to_follow_up` | — | `hours_since_last_contact` (default 24), `limit` (default 10) |

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
| `WEB_SEARCH_PROVIDER` | Gateway — provedor de busca web |
| `FIRECRAWL_API_KEY` | Gateway — scraping via Firecrawl |
| `ZAI_API_KEY` | Gateway — provider z.ai |
| `OPENAI_CODEX` | Gateway — provider OpenAI Codex |

---

## Regra

Toda nova integração externa deve ser documentada aqui.
Toda nova variável de ambiente deve ser adicionada ao `.env.example`.
