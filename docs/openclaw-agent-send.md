# OpenClaw — Agent Send

> **Resumo:** Permite rodar um turno de agente via linha de comando, sem mensagem de chat, útil para automações, testes e entregas programáticas.

---

## Como usar

### 1. Rodar um turno simples
```sh
openclaw agent --message "What is the weather today?"
```

### 2. Alvo específico (agente, sessão ou destino)
```sh
# Agente específico
openclaw agent --agent ops --message "Summarize logs"

# Telefone (gera session key)
openclaw agent --to +15555550123 --message "Status update"

# Sessão existente
openclaw agent --session-id abc123 --message "Continue the task"
```

### 3. Entregar resposta em canal
```sh
# WhatsApp (padrão)
openclaw agent --to +15555550123 --message "Report ready" --deliver

# Slack
openclaw agent --agent ops --message "Generate report" \
  --deliver --reply-channel slack --reply-to "#reports"

# Outro canal
openclaw agent --agent ops --message "Alert" --deliver --reply-channel telegram --reply-to "@admin"
```

---

## Principais flags

| Flag                | Descrição                                                        |
|---------------------|-----------------------------------------------------------------|
| --message <texto>   | Mensagem a enviar (obrigatório)                                  |
| --to <dest>         | Deriva session key (telefone, chat id)                           |
| --agent <id>        | Alvo: agente configurado                                         |
| --session-id <id>   | Reutiliza sessão existente                                       |
| --local             | Força runtime local (ignora Gateway)                             |
| --deliver           | Envia resposta para canal/chat                                   |
| --channel <nome>    | Canal de entrega (whatsapp, telegram, slack, etc.)              |
| --reply-to <alvo>   | Alvo de entrega (override)                                       |
| --reply-channel <n> | Canal de entrega (override)                                      |
| --reply-account <id>| Conta de entrega (override)                                      |
| --thinking <level>  | Nível de "thinking" (off, minimal, low, medium, high, xhigh)     |
| --verbose <on|full|off> | Verbosidade                                                  |
| --timeout <segundos>| Timeout do agente                                                |
| --json              | Saída estruturada JSON                                           |

---

## Comportamento

- Por padrão, usa o Gateway. Use --local para runtime embutido.
- Se o Gateway estiver offline, faz fallback para local.
- --to deriva session key (grupos/canais isolam, chats diretos colapsam para main).
- Flags thinking/verbose persistem na sessão.
- Saída: texto simples (default) ou --json para payload estruturado.

---

## Exemplos

```sh
# Turno simples com JSON
openclaw agent --to +15555550123 --message "Trace logs" --verbose on --json

# Turno com thinking level
openclaw agent --session-id 1234 --message "Summarize inbox" --thinking medium
```

---

## Referências
- Agent CLI reference
- Sub-agents — background sub-agent spawning
- Sessions — como funcionam as session keys