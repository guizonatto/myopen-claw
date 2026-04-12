# Ferramentas — Usell Sales Workflow

## 1. MCP-CRM (`mcp-crm`)

Registrado em `openclaw.json`. Acesso via MCP stdio.

### Operações disponíveis

| Tool | Campos obrigatórios | Campos opcionais |
|---|---|---|
| `search_contact` | `query` | — |
| `add_contact` | `nome`, `email` | `whatsapp`, `cnpj`, `cnaes` |
| `update_contact` | `contact_id` | `pipeline_status`, `stage`, `icp_type`, `nota`, `whatsapp`, `empresa`, `cargo`, `tipo` |

### Exemplo — buscar contato
```json
{ "tool": "search_contact", "query": "João Silva" }
```

### Exemplo — criar contato novo
```json
{
  "tool": "add_contact",
  "nome": "Maria Doces",
  "email": "maria@gmail.com",
  "whatsapp": "5511999990000"
}
```

### Exemplo — atualizar após interação
```json
{
  "tool": "update_contact",
  "contact_id": "uuid-aqui",
  "pipeline_status": "qualificado",
  "stage": "caos_operacional",
  "icp_type": "A",
  "nota": "Relatou 200 msg/dia no WhatsApp. Labeling aplicado. Próximo: ROI."
}
```

---

## 2. Evolution API (WhatsApp)

Envia mensagens via REST. Variáveis de ambiente necessárias:
- `EVOLUTION_URL` — ex: `http://evolution:8080`
- `EVOLUTION_INSTANCE` — nome da instância conectada
- `EVOLUTION_API_KEY` — token de autenticação

### Enviar mensagem de texto com simulação de digitação

Sempre usar `options.delay` e `options.presence` para simular humano digitando.

```
POST {EVOLUTION_URL}/message/sendText/{EVOLUTION_INSTANCE}
Headers: apikey: {EVOLUTION_API_KEY}

Body:
{
  "number": "5511999990000",
  "text": "Oi João! Tudo bem? Vi seu perfil e...",
  "options": {
    "presence": "composing",
    "delay": 3200
  }
}
```

#### Fórmula do delay (ms)

```python
import random

def human_delay_ms(message: str) -> int:
    """40ms por caractere, jitter aleatório, mín 1500ms, máx 8000ms."""
    base = len(message) * 40
    jitter = random.randint(-400, 600)
    return int(min(max(base + jitter, 1500), 8000))
```

Exemplos:
| Mensagem | Chars | Delay aprox. |
|---|---|---|
| "Oi João! Vi seu perfil" | 22 | ~1.5s |
| "Cara, só de você falar isso eu entendo..." | 45 | ~2.4s |
| "João, olha que doideira — no papel deu 18h/semana..." | 55 | ~3.0s |

### Enviar mídia (imagem/arquivo)
```
POST {EVOLUTION_URL}/message/sendMedia/{EVOLUTION_INSTANCE}
Headers: apikey: {EVOLUTION_API_KEY}

Body:
{
  "number": "5511999990000",
  "mediatype": "image",
  "mimetype": "image/jpeg",
  "caption": "Olha esse resultado de uma das nossas lojistas!",
  "media": "https://url-da-imagem.com/foto.jpg"
}
```

### Regras de uso
- Sempre encapsular o número com DDI: `55` + DDD + número (ex: `5511999990000`)
- Nunca enviar mais de 1 mensagem por vez sem delay entre elas
- Resposta da API: `{ "key": { "id": "msg_id" }, "status": "PENDING" }`

---

---

## 3. Discord (Aprendizado de Objeções e Skill Updates)

Usa o skill `discord-messaging`. Variáveis necessárias:
- `DISCORD_BOT_TOKEN` — token do bot
- `DISCORD_GUILD_ID` — ID do servidor

### Canais gerenciados por esta skill

| Canal | Propósito |
|---|---|
| `#objecoes-usell` | Escalação de objeções novas para validação humana |
| `#skill-updates-usell` | Propostas de atualização de docs da skill |

### Criar canal se não existir

```
skill: discord-messaging
action: create_channel
name: "objecoes-usell"   (ou "skill-updates-usell")
type: text
guild_id: {DISCORD_GUILD_ID}
```

### Enviar mensagem em canal

```
skill: discord-messaging
action: send_message
channel: "objecoes-usell"
content: "🚨 Nova objeção..."
```

### Monitorar resposta (via heartbeat ou trigger Discord)

O agente deve checar os threads dos canais em cada heartbeat. Filtros:
- Thread com `OBJECTION_PENDING_ID` nos últimos 2h → verificar reply do owner
- Detectar `APROVADO` ou `REJEITAR` na resposta

---

## Fluxo completo por mensagem recebida

```
[WhatsApp recebe mensagem]
        │
        ▼
[Skill detecta intent]
        │
        ├─ MCP-CRM: search_contact(query)
        │     ├─ encontrou → contact_id
        │     └─ não achou → add_contact → contact_id
        │
        ├─ Gera resposta (BATTLECARD + SALES_PLAYBOOK)
        │
        ├─ MCP-CRM: update_contact(pipeline_status, stage, icp_type, nota)
        │
        └─ Evolution API: sendText(number, resposta)
```
