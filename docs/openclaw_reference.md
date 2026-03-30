# OpenClaw — Referência Rápida

## O que é o OpenClaw (Node.js)
- Gateway multi-canal para agentes de IA (WhatsApp, Telegram, Discord, iMessage, etc.)
- Self-hosted, open source, extensível via plugins
- Roteamento multiagente, sessões isoladas, suporte a mídia, UI web
- Requisitos: Node.js 24+ recomendado
- Documentação oficial: https://docs.openclaw.ai/

## Como este projeto usa o OpenClaw
- O Gateway OpenClaw (Node.js) faz a ponte entre canais e agentes
- Este repositório implementa agentes Python customizados, que se conectam ao Gateway
- Foco em automação, skills, pipes, crons e deploy distribuído
- Integração com Firecrawl, Telegram, e outros canais via Gateway

## Fluxo típico
1. Usuário envia mensagem via canal (ex: Telegram)
2. Gateway OpenClaw recebe, roteia para agente Python
3. Agente executa skills/pipes, responde via Gateway

## Links úteis
- [Documentação OpenClaw](https://docs.openclaw.ai/)
- [Configuração de canais](https://docs.openclaw.ai/gateway/configuration-reference)
- [Plugins e extensões](https://docs.openclaw.ai/plugins/)
- [Deploy e troubleshooting](https://docs.openclaw.ai/gateway/troubleshooting)
# OpenClaw — Referência Completa

> Fonte: docs.openclaw.ai — crawl exaustivo em 2026-03-28 (~60 páginas rastreadas)
> Atualizar este arquivo a cada novo fetch da documentação.

---

## O que é o OpenClaw

Gateway auto-hospedado que conecta apps de chat (WhatsApp, Telegram, Discord, iMessage, Slack, Signal, Mattermost e mais) a agentes de IA.

**Instalação rápida:**
```bash
# macOS/Linux
curl -fsSL https://openclaw.ai/install.sh | bash

# Windows (PowerShell)
iwr -useb https://openclaw.ai/install.ps1 | iex

# npm
npm install -g openclaw@latest
```

**Requisito:** Node.js 24 (Node 22.14+ suportado) + chave de API de um provedor (Anthropic, OpenAI, Google, etc.)

---

## Arquitetura e Estrutura de Diretórios

```
[Canal (WhatsApp/Telegram/...)]
       |
  [Gateway WebSocket :18789]
       |
   [Agente (agentId)]
       |
  [Ferramentas / Sandbox]
       |
  [Provedor de Modelo (Anthropic/OpenAI/...)]
```

```
~/.openclaw/
  openclaw.json                    # config principal (JSON5)
  workspace/                       # workspace do agente default
  agents/<agentId>/
    agent/auth-profiles.json       # credenciais por agente
    sessions/                      # histórico de sessões (.jsonl)
  credentials/
    whatsapp/<accountId>/creds.json
    telegram-allowFrom.json
    <channel>-pairing.json
    <channel>-allowFrom.json
  hooks/                           # hooks gerenciados pelo usuário
  logs/commands.log
  devices/
    pending.json
    paired.json
  exec-approvals.json
```

---

## Configuração (`~/.openclaw/openclaw.json`)

Formato JSON5. Hot reload automático. Validação de schema estrita — gateway não inicia com config inválida.

**Editar via CLI:**
```bash
openclaw config get <path>
openclaw config set <path> <value>
openclaw config unset <path>
```

**Variáveis de ambiente:** carregadas do processo, `.env`, ou `~/.openclaw/.env`. Substituição via `${VAR_NAME}`.

**Config Includes:**
```json5
{ "$include": "./extra-config.json" }
```

**Secret References (para credenciais):**
```json5
{
  "channels": {
    "telegram": {
      "botToken": { "type": "env", "name": "TELEGRAM_BOT_TOKEN" }
    }
  }
}
```

**Modos de Hot Reload:**
| Modo | Comportamento |
|---|---|
| `hybrid` (default) | Mudanças seguras instantâneas; críticas causam restart automático |
| `hot` | Apenas mudanças seguras; avisos para mudanças que precisam restart |
| `restart` | Restart completo a qualquer mudança |
| `off` | Restart manual necessário |

**Variáveis de ambiente globais:**
| Variável | Função |
|---|---|
| `OPENCLAW_HOME` | Ajusta resolução de caminhos internos |
| `OPENCLAW_STATE_DIR` | Customiza diretório de estado |
| `OPENCLAW_CONFIG_PATH` | Especifica arquivo de config customizado |

**Exemplo de config endurecida (baseline seguro):**
```json5
{
  gateway: {
    mode: "local",
    bind: "loopback",
    auth: { mode: "token", token: "replace-with-long-random-token" },
  },
  session: { dmScope: "per-channel-peer" },
  tools: {
    profile: "messaging",
    deny: ["group:automation", "group:runtime", "group:fs", "sessions_spawn", "sessions_send"],
    fs: { workspaceOnly: true },
    exec: { security: "deny", ask: "always" },
    elevated: { enabled: false },
  },
  channels: {
    whatsapp: { dmPolicy: "pairing", groups: { "*": { requireMention: true } } },
  },
}
```

---

## Onboarding / Wizard

```bash
openclaw onboard --install-daemon
```

Cobre 7 etapas: Model/Auth → Workspace → Gateway → Channels → Daemon → Health check → Skills

**Flags:**
- `--reset` — apaga config existente
- `--non-interactive` — deploys scriptados
- `--skip-health` — pula verificação de gateway ativo

**Reconfigurar:**
```bash
openclaw configure
openclaw configure --section web
openclaw agents add <nome>
```

---

## Canais de Comunicação

### Políticas de acesso DM (comuns a todos os canais)
| Política | Comportamento |
|---|---|
| `pairing` (default) | Remetentes desconhecidos recebem código temporário; precisa aprovação |
| `allowlist` | Apenas IDs/números na lista podem enviar |
| `open` | Qualquer um pode enviar (requer `"*"` em `allowFrom`) |
| `disabled` | DMs ignorados |

Códigos de pairing: 8 caracteres uppercase, expiram em 1 hora, max 3 pendentes por canal.

```bash
openclaw pairing list [channel]
openclaw pairing approve [channel] [CODE]
```

---

### Telegram

**Requisito:** Token do bot via @BotFather.

**Config mínima:**
```json5
{
  channels: {
    telegram: {
      enabled: true,
      botToken: "123:abc",
      dmPolicy: "pairing",
      groups: { "*": { requireMention: true } },
    },
  },
}
```

**Variável de ambiente:** `TELEGRAM_BOT_TOKEN`

**Streaming:**
```json5
{ channels: { telegram: { streaming: "partial" } } }
```

**Inline Buttons:**
```json5
{
  action: "send", channel: "telegram", to: "123456789",
  message: "Choose:",
  buttons: [[{ text: "Yes", callback_data: "yes" }, { text: "No", callback_data: "no" }]],
}
```

**Roteamento por tópico de fórum:**
```json5
{
  channels: {
    telegram: {
      groups: {
        "-1001234567890": {
          topics: {
            "3": { agentId: "zu" },
            "5": { agentId: "coder" }
          }
        }
      }
    }
  }
}
```

**Exec Approvals via Telegram:**
```json5
{
  channels: {
    telegram: {
      execApprovals: { enabled: true, approvers: [123456789], target: "dm" },
    },
  },
}
```

**Webhook (opcional):**
```json5
{
  channels: {
    telegram: {
      webhookUrl: "https://example.com/telegram",
      webhookSecret: "your-secret-key",
      webhookPath: "/telegram-webhook",
      webhookHost: "127.0.0.1",
      webhookPort: 8787,
    },
  },
}
```

**Troubleshooting:**
- Bot ignora mensagens em grupos sem menção: verificar `requireMention=false` e desativar Privacy Mode via `/setprivacy`
- `BOT_COMMANDS_TOO_MUCH`: reduzir plugins ou desativar menus nativos
- Problemas de rede: `dig +short api.telegram.org A`, configurar proxy: `channels.telegram.proxy: "socks5://..."`
- Forçar IPv4: `channels.telegram.network.autoSelectFamily: false`

---

### WhatsApp

Usa WhatsApp Web (Baileys).

**Setup:**
```bash
openclaw channels add --channel whatsapp
openclaw channels login --channel whatsapp   # QR Code
openclaw gateway
openclaw pairing approve whatsapp <CODE>
```

**Instalação manual:** `openclaw plugins install @openclaw/whatsapp`

**Configurações:**
- Chunking de texto: 4000 chars (padrão), modos "length" ou "newline"
- Media: imagens, vídeo, áudio, documentos — limite 50MB (padrão)
- Histórico de grupos: 50 mensagens (configurável via `historyLimit`)
- Multi-conta: `~/.openclaw/credentials/whatsapp/<accountId>/creds.json`

---

### Discord

**Permissões necessárias:**
- Scopes: `bot`, `applications.commands`
- Permissions: View Channels, Send Messages, Read Message History, Embed Links, Attach Files
- Intents obrigatórios: "Message Content Intent" e "Server Members Intent"

**Config com allowlist:**
```json5
{
  channels: {
    discord: {
      groupPolicy: "allowlist",
      guilds: {
        "SERVER_ID": { requireMention: false, users: ["USER_ID"] }
      }
    }
  }
}
```

**Streaming modes:** `off` (default), `partial`, `block`, `progress`

**Block mode chunking:**
```json5
{
  draftChunk: { minChars: 200, maxChars: 800, breakPreference: "paragraph" }
}
```

**Voz:** `/vc join|leave|status` — TTS configurável (ex: OpenAI)

**Histórico:** `historyLimit` default = 20 mensagens em guilds

---

### Slack

**Modo Socket (default):** App Token (`xapp-...`) + Bot Token (`xoxb-...`)
**Modo HTTP Events API:** Bot Token + signing secret

**Scopes necessários:** `chat:write`, `channels:history`, `im:read`, `reactions:write`, `pins:read`, `assistant:write`

**Eventos necessários:** `app_mention`, eventos de mensagem por tipo de conversa

**Streaming:** modos `partial`, `block`, `progress`, `off`

---

### Signal

Usa `signal-cli` via HTTP JSON-RPC + SSE. Requer Linux (Ubuntu 24 testado) e número de telefone dedicado.

**Config mínima:**
```json5
{
  channels: {
    signal: {
      enabled: true,
      account: "+15551234567",
      cliPath: "signal-cli",
      dmPolicy: "pairing",
      allowFrom: ["+15557654321"]
    }
  }
}
```

**Chunking:** 4000 chars (padrão), limite de mídia: 8MB (padrão)

---

### iMessage

Usa `imsg rpc` via JSON-RPC/stdio. **Para novos deployments, usar BlueBubbles.**
Requer Full Disk Access + Automation permission no macOS.

---

### Mattermost (Plugin)

```bash
openclaw plugins install @openclaw/mattermost
```

**Config:** `botToken`, `baseUrl`, `dmPolicy`

**Modos de resposta:** `oncall` (default, só em menção), `onmessage`, `onchar`

**Variáveis:** `MATTERMOST_BOT_TOKEN`, `MATTERMOST_URL`

---

## Agentes e Multi-Agente

**Conceitos:**
- **`agentId`**: "cérebro" com workspace e autenticação próprios
- **`accountId`**: instância de conta de um canal
- **`binding`**: rota mensagens de entrada para agentes por canal, conta e peer

**Ordem de precedência de roteamento (mais específico vence):**
1. Peer ID exato (direto/grupo/canal)
2. Peer pai (herança de thread)
3. Roles + guild do Discord
4. Apenas guild ID
5. Team ID (Slack)
6. Account ID
7. Fallback por canal
8. Agente default

**Config de binding:**
```json5
{
  agentId: "work",
  match: {
    channel: "whatsapp",
    accountId: "biz",
    peer: { kind: "direct", id: "+15551234567" }
  }
}
```

**Multi-conta:**
```bash
openclaw channels login --channel whatsapp --account personal
openclaw channels login --channel whatsapp --account biz
openclaw agents list --bindings
```

---

## System Prompt e Arquivos de Bootstrap

Arquivos auto-injetados no contexto (cada um com limite de 20.000 chars):

| Arquivo | Descrição |
|---|---|
| `AGENTS.md` | Regras de comportamento |
| `SOUL.md` | Personalidade e tom |
| `TOOLS.md` | Instruções de ferramentas |
| `IDENTITY.md` | Identidade do agente |
| `USER.md` | Contexto do usuário |
| `HEARTBEAT.md` | Instruções de heartbeat |
| `MEMORY.md` | Memória de longo prazo |

**Limite total injetado:** 150.000 caracteres.
Sub-agentes recebem apenas `AGENTS.md` e `TOOLS.md`.

**Modos de prompt:** `full` (default), `minimal` (sub-agentes), `none` (só linha de identidade)

---

## Memória

- **`memory/YYYY-MM-DD.md`**: logs diários, append-only
- **`MEMORY.md`**: memória de longo prazo curada

**Ferramentas do agente:**
- `memory_search` — busca semântica sobre snippets indexados
- `memory_get` — leitura de arquivo/intervalo de linhas

**Busca vetorial:** embeddings de OpenAI, Gemini, Voyage, Mistral, Ollama, GGUF local. Busca híbrida: BM25 + similaridade vetorial.

**Flush automático:** antes de compactação de contexto, turno silencioso preserva informações importantes (retorna `NO_REPLY`).

---

## Sessões

**Escopos de DM (`dmScope`):**
| Escopo | Isolamento |
|---|---|
| `main` (default) | Todos os DMs compartilham sessão principal |
| `per-peer` | Isolado por identidade do remetente |
| `per-channel-peer` | Isolado por canal + remetente (padrão do onboarding) |
| `per-account-channel-peer` | Inclui conta |

**Ciclo de vida:**
- Reset diário às 4:00 AM (horário local do gateway)
- `idleMinutes`: janela de ociosidade opcional
- Comandos manuais: `/new`, `/reset`

**Manutenção de armazenamento (defaults):** 30 dias de retenção, cap de 500 entradas, rotação de transcripts em 10MB.

---

## Automação

### Cron vs Heartbeat

| Aspecto | Heartbeat | Cron |
|---|---|---|
| Timing | Intervalos regulares (default 30min) | Expressão cron com timezone |
| Sessão | Sessão principal | Sessão isolada (opcional) |
| Uso ideal | Múltiplas verificações agrupadas | Tarefa única em horário exato |
| Custo API | Menor (batching) | Por job |

**Heartbeat config:**
```json5
{
  heartbeat: {
    every: "30m",
    target: "last",
    activeHours: { start: "08:00", end: "22:00" }
  }
}
```

**Estratégia ótima:** heartbeat para monitoramento rotineiro + cron para agendamentos precisos e lembretes one-shot.

---

### Standing Orders (AGENTS.md)

Componentes obrigatórios por programa:
1. **Scope** — ações autorizadas e limites
2. **Triggers** — quando executar
3. **Approval gates** — ações que precisam de aprovação humana
4. **Escalation rules** — condições para intervenção humana

**Padrão recomendado:** Execute-Verify-Report.

---

### Hooks

**Categorias de eventos:**
- `command:new`, `command:reset`, `command:stop`
- `session:compact:before`, `session:compact:after`, `session:patch`
- `agent:bootstrap`, `gateway:startup`
- `message:received`, `message:transcribed`, `message:preprocessed`, `message:sent`

**Hooks bundled:**
| Hook | Função |
|---|---|
| `session-memory` | Salva snapshots de sessão em `~/.openclaw/workspace/memory/` |
| `bootstrap-extra-files` | Injeta arquivos extras na inicialização do agente |
| `command-logger` | Audit trail em `~/.openclaw/logs/commands.log` (JSONL) |
| `boot-md` | Executa `BOOT.md` quando o gateway inicia |

**Config:**
```json5
{
  hooks: {
    internal: {
      enabled: true,
      entries: {
        "session-memory": { enabled: true },
        "command-logger": { enabled: false }
      }
    }
  }
}
```

**CLI:**
```bash
openclaw hooks list
openclaw hooks enable <name>
openclaw hooks info <name>
openclaw hooks check
```

**Estrutura de hook customizado:** `HOOK.md` (YAML frontmatter) + `handler.ts` (exporta `HookHandler`)

**Hierarquia (menor → maior precedência):** bundled → plugin → managed → workspace

---

## Ferramentas (Tools)

### Browser

Automação com Chrome/Brave/Edge/Chromium via CDP isolado.

**Perfis:** `openclaw` (isolado), `user` (Chrome DevTools MCP), Remote CDP (Browserless, Browserbase)

**Config:**
```json5
{
  browser: {
    enabled: true,
    defaultProfile: "openclaw",
    ssrfPolicy: { dangerouslyAllowPrivateNetwork: false }
  }
}
```

**Serviços remotos:**
```
wss://production-sfo.browserless.io?token=<API_KEY>
wss://connect.browserbase.com?apiKey=<API_KEY>
```

**CLI:**
```bash
openclaw browser start|stop|status
openclaw browser open <url>
openclaw browser click <ref>
openclaw browser type <ref> "texto"
openclaw browser snapshot
openclaw browser screenshot
```

Requer Playwright para features avançadas (navigate, act, AI snapshot, PDF).

---

### Exec

**Hosts:** `sandbox` (default, container isolado), `gateway` (host com aprovações), `node` (companion/headless)

```bash
openclaw config set tools.exec.security allowlist
openclaw config set tools.exec.host node
```

---

### Exec Approvals

| Modo | Comportamento |
|---|---|
| `deny` | Bloqueia toda execução no host |
| `allowlist` | Permite apenas comandos pré-aprovados |
| `full` | Permite tudo |

**Ask behavior:** `off`, `on-miss`, `always`

**Safe Bins (sem aprovação):** `cut`, `uniq`, `head`, `tail`, `tr`, `wc`

**Aprovação via chat:** `/approve <id> [allow-once|allow-always|deny]`

---

### PDF

- Até 10 PDFs por chamada, 10MB/doc, 20 páginas (configurável)
- Aceita: caminhos locais, `file://`, `http(s)://`
- Modo nativo (Anthropic/Google) vs fallback (extrai texto + imagens)
- Parâmetro `pages` incompatível com modo nativo

---

## Nodes (Dispositivos)

Dispositivos companion conectados ao Gateway WebSocket com `role: "node"`.
Plataformas: macOS (menubar), iOS/Android, Linux/Windows/macOS headless.

**Setup de node remoto:**
```bash
openclaw node run --host <gateway-host> --port 18789 --display-name "Build Node"
openclaw node install --host <gateway-host> --port 18789
openclaw devices approve <requestId>
openclaw approvals allowlist add --node <id|name|ip> "/usr/bin/uname"
openclaw config set tools.exec.host node
```

**SSH Tunnel:**
```bash
ssh -N -L 18790:127.0.0.1:18789 user@gateway-host
export OPENCLAW_GATEWAY_TOKEN="<token>"
openclaw node run --host 127.0.0.1 --port 18790
```

**Comandos disponíveis nos nodes:**
```
canvas.snapshot    canvas.present    canvas.eval    canvas.navigate
camera.snap        camera.clip
location.get
motion.activity    motion.pedometer
screen.record
device.status      device.info       device.permissions    device.health
notifications.list notifications.actions
sms.send           contacts.search   calendar.events       callLog.search
photos.latest
system.run         system.notify     system.which
system.execApprovals.get/set
```

**CLI para nodes:**
```bash
openclaw devices list
openclaw nodes status
openclaw nodes describe --node <idOrNameOrIp>
openclaw nodes canvas snapshot --node <id> --format png
openclaw nodes camera snap --node <id> --facing front
openclaw nodes run --node <id> -- echo "Hello"
openclaw nodes notify --node <id> --title "Ping" --body "Ready"
```

---

## Sandboxing

| Modo | Ativação |
|---|---|
| `"off"` | Desativado |
| `"non-main"` | Apenas sessões não-principais (recomendado) |
| `"all"` | Toda sessão em container |

**Backends:** Docker (local), SSH (remoto), OpenShell (gerenciado com sync de workspace)

**OpenShell workspace models:** `mirror` (local canônico), `remote` (sandbox canônico)

Imagem default: `openclaw-sandbox:bookworm-slim`. `tools.elevated` escapa intencionalmente do sandbox.

---

## Provedores de Modelo

Formato: `provider/model` (ex: `anthropic/claude-sonnet-4-6`). Suporte a 35+ provedores.
Self-hosted: vLLM, SGLang, Ollama, qualquer endpoint compatível OpenAI/Anthropic.

**Failover:** rotação por perfis → fallback para modelos configurados
**Cooldowns exponenciais:** 1min → 5min → 25min → 1h

**Seleção manual:** `/model Opus@anthropic:work`

**Config de fallbacks:**
```json5
{
  agents: {
    defaults: {
      model: { fallbacks: ["openai/gpt-4o", "google/gemini-2.5-pro"] }
    }
  }
}
```

---

## Streaming e Chunking

1. **Block streaming (canais):** entrega blocos completos conforme ficam disponíveis
2. **Preview streaming (Telegram/Discord/Slack):** atualiza mensagem temporária durante geração

> Não há streaming true de token-delta para mensagens de canais.

```json5
{
  agents: {
    defaults: {
      blockStreamingDefault: "on",
      blockStreamingBreak: "text_end",
      blockStreamingChunk: {
        minChars: 200, maxChars: 800,
        breakPreference: "paragraph"  // paragraph > newline > sentence > whitespace > hard
      },
      humanDelay: { mode: "natural" }  // "off" | "natural" (800-2500ms) | "custom"
    }
  }
}
```

**Preview streaming por canal:**
| Canal | off | partial | block | progress |
|---|---|---|---|---|
| Telegram | sim | sim | sim | maps to partial |
| Discord | sim | sim | sim | maps to partial |
| Slack | sim | sim | sim | sim |

---

## Segurança

**Modelo:** uma fronteira de operador confiável por gateway. Multi-tenant com confiança mista → gateways separados.

**Permissões recomendadas:** `openclaw.json` = `600`, dir `~/.openclaw` = `700`

**Contenção em incidente:**
1. Encerrar gateway
2. Definir `gateway.bind: "loopback"`, desativar Tailscale Funnel/Serve
3. Mudar DMs/grupos de risco para `disabled`

**Rotação:**
1. Alterar `gateway.auth.token` e reiniciar
2. Rotacionar credenciais de provedores e chaves de API

**Auditoria:**
```bash
openclaw security audit --deep --fix --json
```

**Ferramentas de alto risco — negar por padrão:**
```json5
{ tools: { deny: ["gateway", "cron", "sessions_spawn", "sessions_send"] } }
```

**Prompt Injection — mitigações:** pairing/allowlists, `requireMention` em grupos, sandboxing, modelos mais novos.

**Relato:** security@openclaw.ai

---

## Acesso Remoto

```bash
ssh -N -L 18789:127.0.0.1:18789 user@host
```

**Cenários:** VPS always-on com Tailscale, desktop macOS com app gerenciando tunnel SSH, gateway local via SSH tunnel/Tailscale Serve.

**Credenciais remotas (precedência):** CLI args > env (`OPENCLAW_GATEWAY_TOKEN`/`OPENCLAW_GATEWAY_PASSWORD`) > config (`gateway.remote.token`)

---

## Control UI

SPA em `http://<host>:18789/`. Localidades: EN, ZH-CN, ZH-TW, PT-BR, DE, ES.

Funcionalidades: chat com streaming ao vivo, gerenciamento de canais (QR), cron jobs, skills, nodes, aprovações de exec, edição de config, logs ao vivo, health snapshots.

Tokens devem usar fragmentos de URL (`#token=...`) para evitar logging server-side.

---

## Audio e Voz

**Transcrição (ordem):** `sherpa-onnx-offline` → `whisper-cli` → `whisper` → Gemini CLI → OpenAI → Groq → Deepgram → Google

- Limite: 20MB (`maxBytes`), arquivos < 1024 bytes ignorados
- OpenAI default: `gpt-4o-mini-transcribe`
- Desativar: `tools.media.audio.enabled: false`

---

## Plugins

```bash
openclaw plugins install <package-name>
```

| Plugin | Pacote |
|---|---|
| DingTalk | `@largezhou/ddingtalk` |
| Lossless Claw (LCM) | `@martian-engineering/lossless-claw` |
| Opik (monitoramento) | `@opik/opik-openclaw` |
| QQbot | `@sliverp/qqbot` |
| WeCom | `@wecom/wecom-openclaw-plugin` |
| WhatsApp | `@openclaw/whatsapp` |
| Mattermost | `@openclaw/mattermost` |

---

## Context Engine

Ciclo de vida: **Ingest** → **Assemble** → **Compact** → **After turn**

Engine default: `legacy`. Customizar via plugin:
```json5
{ plugins: { slots: { contextEngine: "meu-plugin-id" } } }
```

---

## Logging

- Console: `logging.consoleLevel` (`error`/`warn`/`info`/`debug`/`trace`), `logging.consoleStyle` (`pretty`/`compact`/`json`)
- Arquivo: `/tmp/openclaw/openclaw-YYYY-MM-DD.log` (rolling diário)
- Redação: `logging.redactSensitive: "tools"` (default)

```bash
openclaw logs --follow
openclaw gateway --verbose --ws-log compact
```

---

## Plataformas

**macOS:** menu-bar companion, gerencia LaunchAgent `ai.openclaw.gateway`, deep link `openclaw://`. Evitar diretórios com sync de nuvem.

**Windows (WSL2):**
```powershell
wsl --install -d Ubuntu
```
```bash
# habilitar systemd em /etc/wsl.conf
sudo loginctl enable-linger "$(whoami)"
openclaw gateway install
```

**Docker:**
```bash
export OPENCLAW_IMAGE="ghcr.io/openclaw/openclaw:latest"
./scripts/docker/setup.sh
```
Variáveis: `OPENCLAW_EXTENSIONS`, `OPENCLAW_EXTRA_MOUNTS`, `OPENCLAW_HOME_VOLUME`, `OPENCLAW_SANDBOX`

---

## Diagnósticos CLI

```bash
openclaw status [--all] [--deep]
openclaw health --json
openclaw gateway status
openclaw logs --follow
openclaw doctor [--fix]
openclaw channels status --probe
openclaw security audit --deep
```

---

## Informações adicionais coletadas no crawl de 2026-03-28

### Gateway — Tailscale
URL: /gateway/tailscale

**Modos operacionais:**
- **Serve**: acesso apenas na tailnet via `tailscale serve` — gateway no loopback, Tailscale gerencia HTTPS e roteamento
- **Funnel**: acesso HTTPS público via `tailscale funnel` — requer senha compartilhada
- **Off**: padrão, sem automação

**Autenticação via Tailscale:** Com Serve + `gateway.auth.allowTailscale`, não precisa de credenciais.

> "Endpoints `/v1/*`, `/tools/invoke` e `/api/channels/*` ainda requerem auth token/password."

**Restrições do Funnel:** Tailscale v1.38.3+, MagicDNS, HTTPS ativo, portas 443/8443/10000.

---

### Gateway — Secrets Management
URL: /gateway/secrets

Segredos resolvidos para snapshot de runtime em memória durante ativação, não lazily durante requests.

**Três tipos de fonte (SecretRefs):**
1. `source: "env"` — env var (`^[A-Z][A-Z0-9_]{0,127}$`)
2. `source: "file"` — JSON pointers com escaping RFC6901
3. `source: "exec"` — binários com protocolos stdin/stdout estruturados

Refs não resolvidas em surfaces inativas **não bloqueiam** startup.

```bash
openclaw secrets audit --check
openclaw secrets configure
openclaw secrets apply
```

---

### Gateway — Protocol
URL: /gateway/protocol

WebSocket com frames de texto JSON. Duas roles: **Operator** (control plane: CLI, web UI, automação) e **Node** (câmera, tela, canvas, system.run).

**Autenticação:** Clients devem assinar nonce do servidor com identidade de dispositivo derivada de keypair. Tokens emitidos por dispositivo + role.

**Escopos de Operator:** `operator.read`, `operator.write`, `operator.admin`

**Versionamento:** Clients enviam `minProtocol` + `maxProtocol`; servidor rejeita mismatches.

---

### Gateway — Background Exec e Process Tool
URL: /gateway/background-process

**exec tool** — parâmetros: `command`, `yieldMs` (10000ms), `background`, `timeout` (1800s), `elevated`, `pty`, `workdir`, `env`. Spawn com contexto `OPENCLAW_SHELL=exec`.

**process tool** — ações: `list`, `poll`, `log` (últimas 200 linhas), `write` (stdin), `kill`, `clear`, `remove`.

> Sessões em background não sobrevivem a reinicializações do processo.

---

### Gateway — OpenShell
URL: /gateway/openshell

Backend de sandbox gerenciado. Dois modos de workspace:
- **Mirror**: workspace local é fonte da verdade, sincroniza antes/depois de cada execução
- **Remote**: workspace OpenShell é canônico após seeding inicial; menor overhead por turno

Diretório workspace remoto padrão: `/sandbox`. Browser sandbox não suportado no OpenShell.

---

### Gateway — Doctor
URL: /gateway/doctor

```bash
openclaw doctor                        # modo interativo
openclaw doctor --yes                  # aceita defaults
openclaw doctor --repair               # aplica correções sem prompt
openclaw doctor --repair --force       # reparos agressivos
openclaw doctor --non-interactive      # apenas migrações seguras
openclaw doctor --deep                 # escaneia system services
openclaw doctor --generate-gateway-token  # gera novo token
```

---

### Automação — Cron Jobs (detalhes completos)
URL: /automation/cron-jobs

Cron roda **dentro do Gateway** (não dentro do modelo). Jobs persistem em `~/.openclaw/cron/`, sobrevivendo a restarts.

**Tipos de schedule:**
- `at`: timestamp one-shot ISO 8601
- `every`: intervalo fixo em milissegundos
- `cron`: expressões 5 ou 6 campos com timezone IANA opcional; stagger automático para topo de hora

**Modos de entrega:**
- `announce`: channel adapters (Slack, Discord, Telegram, WhatsApp, etc.)
- `webhook`: POSTs de payloads para URLs
- `none`: interno, sem entrega

**Retry:** transientes com backoff exponencial; permanentes desabilitam imediatamente. One-shot: até 3 retries.

**Storage:** `~/.openclaw/cron/jobs.json`. Histórico: `cron/runs/<jobId>.jsonl`. Sessões isoladas expiram por `cron.sessionRetention` (padrão: 24 horas).

```bash
openclaw cron add / edit / list / run / remove
openclaw cron runs    # histórico de execuções
```

---

### Automação — Webhooks
URL: /automation/webhook

```json
{
  "enabled": true,
  "token": "<shared-secret>",
  "path": "/hooks"
}
```

`hooks.token` é obrigatório quando `hooks.enabled=true`.

**Autenticação:** `Authorization: Bearer <token>` ou `x-openclaw-token: <token>`. Tokens via query-string rejeitados com 400.

**POST /hooks/wake** — enfileira sistema event na sessão principal (`mode: "now"` ou `"next-heartbeat"`).
**POST /hooks/agent** — roda turno isolado de agente com parâmetros customizáveis (mensagem, agente, modelo, canal de entrega).

**Features avançadas:** transforms JavaScript/TypeScript para payloads arbitrários, presets built-in para Gmail via Pub/Sub.

---

### Canais — IRC
URL: /channels/irc

Config via `~/.openclaw/openclaw.json` com host, port, TLS, nick, target channels. DMs: `"pairing"` por padrão. Grupos: `"allowlist"` por padrão. Para canais públicos, restringir ferramentas: `toolsBySender`. NickServ auth suportado.

---

### Canais — LINE
URL: /channels/line

```bash
openclaw plugins install @openclaw/line
```
Channel access token + Channel secret do LINE Developer Console. Webhook HTTPS em `https://gateway-host/line/webhook`. Chunking: 5.000 chars. Suporta Flex messages, template messages, quick replies. Não suporta: reactions, threads.

---

### Canais — Nostr
URL: /channels/nostr

Protocolo descentralizado via NIP-04 (encrypted DMs). Private key em `nsec` ou hex. Relays padrão: Damus e nos.lol. NIP-17 e NIP-44 planejados. MVP: apenas DMs, sem attachments.

---

### Canais — Zalo
URL: /channels/zalo

```bash
openclaw plugins install @openclaw/zalo
```
Experimental. Plataforma focada no Vietnã. Suporta DMs de texto (2000 chars). Não suporta: groups, reactions, threads, streaming. `ZALO_BOT_TOKEN=...`

---

### Canais — Google Chat
URL: /channels/googlechat

1. Habilitar Google Chat API no Google Cloud, criar service account com chave JSON
2. Configurar Chat app com HTTP endpoint
3. Armazenar credenciais como env vars
4. Expor webhook com segurança (Tailscale Funnel, Caddy, Cloudflare Tunnel)

> "Exponha apenas o caminho `/googlechat`." Mídia até 20MB por padrão.

---

### Canais — Broadcast Groups
URL: /channels/broadcast-groups

Feature experimental (v2026.1.9+). Permite múltiplos agentes processarem a mesma mensagem em WhatsApp com isolamento completo de sessão.

**Estratégias:** `parallel` (padrão) ou `sequential`.

Expansão planejada para Telegram, Discord, Slack.

---

### Canais — Channel Routing
URL: /channels/channel-routing

OpenClaw rota respostas **de volta ao canal de origem**. Prioridade de seleção de agente (inbound):
1. Peer match exato via bindings
2. Parent peer/thread inheritance
3. Discord guild + roles
4. Guild matching
5. Slack team
6. Account ID
7. Channel-wide
8. Default agent fallback

Sessões: DMs → `agent:<agentId>:<mainKey>`, Grupos → `agent:<agentId>:<channel>:group:<id>`, Threads → append `:thread:<threadId>`.

---

### Tools — Slash Commands (detalhes)
URL: /tools/slash-commands

**Directives** (strippadas antes do modelo): `/think`, `/fast`, `/verbose`, `/reasoning`, `/elevated`, `/exec`, `/model`, `/queue`

**Inline shortcuts** (executam imediatamente): `/help`, `/commands`, `/status`, `/whoami`

**Configuração de segurança:**
```json5
{
  "commands.bash": false,
  "commands.config": false,
  "commands.mcp": false,
  "commands.plugins": false,
  "commands.debug": false,
  "commands.text": true
}
```

Comandos notáveis: `/tools`, `/model`, `/debug`, `/config`, `/btw` (perguntas efêmeras), `/skill`, `/compact`.

"Fast path: mensagens command-only de remetentes na allowlist são tratadas imediatamente (bypass queue + model)."

---

### Tools — ACP Agents
URL: /tools/acp-agents

ACP (Agent Client Protocol) permite OpenClaw operar ambientes externos: Codex, Claude Code, Cursor, Gemini CLI.

```bash
/acp spawn codex --bind here
/acp status
/acp cancel
/acp close
```

**Config obrigatória:** `acp.enabled: true`, `backend: "acpx"`, `defaultAgent`, `allowedAgents`.

> "Sessões em sandbox não podem spawnar ACP sessions porque `runtime='acp'` roda no host."

---

### Tools — Lobster
URL: /tools/lobster

Shell de workflow para sequências multi-step determinísticas com checkpoints de aprovação explícitos. Uma chamada em vez de muitas. Workflows pausados são resumíveis via tokens.

Usar `alsoAllow: ["lobster"]` em vez de allowlists restritivas.

---

### Tools — LLM Task
URL: /tools/llm-task

Plugin executando operações LLM retornando JSON estruturado e validado. Sem ferramentas expostas ao modelo para o run. Parâmetros: `prompt`, input data, JSON Schema, provider/model, reasoning level, auth, temperature, token limits, timeout.

---

### Tools — Diffs
URL: /tools/diffs

Transforma mudanças de texto em diff artifacts. Modos: `"view"` (viewer URLs), `"file"` (PNG/PDF), `"both"`. Limites: 512 KiB por bloco, 2 MiB para patches. TTL: 30 minutos (máximo 6 horas). Requer Chromium para modo `"file"`.

---

### Skills
URL: /tools/skills  |  /tools/creating-skills

Skills são diretórios com `SKILL.md` (YAML frontmatter + instruções).

**Hierarquia de carregamento (maior → menor prioridade):**
1. `<workspace>/skills`
2. `<workspace>/.agents/skills`
3. `~/.agents/skills`
4. `~/.openclaw/skills`
5. Bundled skills
6. Extra skill directories

**Campos SKILL.md obrigatórios:** `name` (snake_case único), `description`.

**ClawHub Registry:** `openclaw skills install <skill-name>` — https://clawhub.com

**Custo de tokens:** ~195 chars base + ~97 chars por skill.

**Criação:**
```bash
mkdir ~/.openclaw/workspace/skills/minha-skill
# criar SKILL.md com frontmatter + instruções
openclaw skills list    # verificar carregamento
```

---

### Sub-Agents
URL: /tools/subagents

Runs em background spawned de sessões existentes. Operam independentemente.

```bash
/subagents list / kill / spawn
# tool: sessions_spawn (retorna run ID imediatamente)
```

- `maxSpawnDepth: 1` (padrão): sem filhos
- `maxSpawnDepth: 2`: padrão orquestrador
- "Sub-agentes recebem todas as ferramentas exceto session tools e system tools"
- Concorrência padrão: 8, auto-arquiva após 60 minutos

---

### Concepts — Agent Workspace
URL: /concepts/agent-workspace

Workspace padrão: `~/.openclaw/workspace`. Com profiles: `~/.openclaw/workspace-<profile>`.

**Arquivos padrão:** `AGENTS.md`, `SOUL.md`, `USER.md`, `IDENTITY.md`, `TOOLS.md`, `memory/YYYY-MM-DD.md`

> "O workspace é o **cwd padrão**, não um sandbox hard." Paths absolutos ainda acessam outros locais do host.

**Segurança:** armazenar em repositório git privado, evitar secrets e API keys no workspace.

---

### Concepts — Compaction
URL: /concepts/compaction

"Compaction **sumariza conversação mais antiga** e mantém mensagens recentes intactas." Persiste em JSONL.

- Auto: ativa próximo aos limites de contexto
- Manual: `/compact [instruções]`
- Pode usar modelo separado para summarização

"Compaction: persiste em JSONL. Session pruning: trimma apenas tool results em memória, por request."

---

### Concepts — Session Pruning
URL: /concepts/session-pruning

Ativa quando `mode: "cache-ttl"` e última chamada Anthropic é mais antiga que o `ttl`. Apenas mensagens `toolResult` são trimadas. Últimas 3 mensagens de assistente preservadas. Tool results com image blocks nunca são prunados.

**Métodos:** soft-trim (abrevia preservando início e fim) ou hard-clear (substitui com placeholder).

---

### Platforms — iOS
URL: /platforms/ios

Node conectando-se ao Gateway via WebSocket. Conexão: LAN via Bonjour, Tailnet via unicast DNS-SD, ou Manual. Push notifications via sistema relay-backed.

Limitações: `NODE_BACKGROUND_UNAVAILABLE` (precisa foreground), `A2UI_HOST_NOT_CONFIGURED`.

---

### Platforms — Android
URL: /platforms/android

App não lançado publicamente. Build manual: `./gradlew :app:assemblePlayDebug`. Conexão via mDNS/NSD + WebSocket (`ws://<host>:18789`). Features: canvas, câmera, voice/TTS, dados do dispositivo (contatos, calendário, SMS, notificações).

---

### Install — Docker VM Runtime
URL: /install/docker-vm-runtime

Todos os binários externos devem ser **baked na imagem em tempo de build**, nunca instalados em runtime (perdidos no restart). Para ARM (Hetzner ARM, GCP Tau T2A): substituir variantes ARM64.

---

### Install — Hetzner
URL: /install/hetzner

OpenClaw 24/7 por ~$5 em VPS Hetzner. Infraestrutura via Terraform: `https://github.com/andreesg/openclaw-terraform-hetzner`.

---

### OpenProse
URL: /prose

Formato markdown-first para orquestrar sessões de IA via arquivos `.prose`. Instalação: `openclaw plugins enable open-prose`.

```bash
/prose run <file.prose>
/prose compile <file.prose>
/prose examples
```

Mapeia para: `sessions_spawn`, `read`/`write`, `web_fetch`. Storage: filesystem (padrão), SQLite, PostgreSQL (experimental).

---

### CLI — Devices
URL: /cli/devices

```bash
openclaw devices list / approve [id] / reject <id> / remove <id> / clear --yes
openclaw devices rotate <id>      # novo token (sensível)
openclaw devices revoke <role>    # remover tokens por role
```
Requer `operator.pairing` ou `operator.admin`.

---

### CLI — Security
URL: /cli/security

```bash
openclaw security audit [--deep] [--fix] [--json]
```

Verifica: sessões DM multi-usuário compartilhadas, modelos pequenos sem sandboxing, segurança de webhook, exposição de rede, integridade de plugins.

`--fix` aplica automaticamente: conversão de policies "open" → allowlists, redação de logs sensíveis, permissões de arquivo. Não rotaciona credenciais, não desabilita ferramentas.

---

### CLI — System
URL: /cli/system

```bash
openclaw system event --text "mensagem" --mode now
openclaw system heartbeat enable / disable / last
openclaw system presence [--json]
```

> "System events são efêmeros e não persistem entre restarts."

---

### Reference — Credits
URL: /reference/credits

**Nome:** "CLAW + TARDIS". **Criador:** Peter Steinberger. **Segurança:** Mario Zechner.

**Contribuidores:** Maxim Vovshin (skill Blogwatcher), Nacho Iacovino (parsing de localização Telegram/WhatsApp), Vincent Koc (agentes, telemetria, hooks, segurança).

**Licença:** MIT.

---

### Páginas com 404 (tentadas neste crawl)

- `/concepts/agent-runtime`, `/concepts/gateway-architecture`
- `/channels/webchat`, `/channels/teams` (Microsoft Teams: disponível como plugin)
- `/channels/voice-call`
- `/nodes/talk-mode`, `/nodes/voice-wake`
- `/tools/files`, `/tools/code`, `/tools/mcp`, `/tools/mcp-tools`
- `/tools/search` → URL correta: `/tools/web`
- `/tools/sub-agents` → URL correta: `/tools/subagents`
- `/reference/cli`, `/reference/config`, `/reference/changelog`
- `/automation/cron` → URL correta: `/automation/cron-jobs`
- `/automation/webhooks` → URL correta: `/automation/webhook`
- `/plugins/building` → URL correta: `/plugins/building-plugins`
- `/gateway/auth`, `/gateway/background` → URL correta: `/gateway/background-process`