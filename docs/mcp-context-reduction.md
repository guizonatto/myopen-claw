# MCP Context Reduction — Guia Canônico

## Por que fazer isso

O OpenClaw injeta o schema de **todas** as tools de cada MCP no system prompt do agente antes de qualquer chamada ao LLM. Um MCP com 25 tools gera ~14k chars de schema — mesmo que o agente use apenas 2 delas.

Para modelos com janela limitada (Groq 6-12k TPM, zai 10 RPM), isso causa:
- `413 Request too large`
- Fallback para modelos mais caros
- `bundle-tools > 30s` por starvation do event loop

### Medição real neste projeto

| Configuração | Schema MCP | Contexto total cold-contact |
|---|---|---|
| mcp-crm direto (25 tools) | ~14k chars / ~3.5k tokens | ~31k chars / ~7.8k tokens |
| crm-proxy (1 tool) | ~524 chars / ~131 tokens | ~8k chars / ~2k tokens |
| **Redução** | **96%** | **74%** |

---

## Como fazer: padrão proxy

### 1. Criar `proxy.py` dentro do diretório do MCP

O proxy é um servidor MCP stdio que expõe **uma única tool genérica** e delega para as funções reais do MCP original via importação direta (sem HTTP, sem auth overhead).

```python
# mcps/meu_mcp/proxy.py
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool
import asyncio, json

CRM_TOOL = Tool(
    name="crm",
    description="Execute a CRM operation. Available actions and params in AGENTS.md.",
    inputSchema={
        "type": "object",
        "properties": {
            "action": {"type": "string", "description": "Operation name"},
            "params": {"type": "object", "additionalProperties": True},
        },
        "required": ["action"],
    },
)

mcp_server = Server("crm-proxy")

@mcp_server.list_tools()
async def list_tools():
    return [CRM_TOOL]

@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict):
    from main import execute_crm, CRMRequest
    req = CRMRequest(operation=arguments["action"], **(arguments.get("params") or {}))
    result = execute_crm(req)
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]

async def main():
    async with stdio_server() as (r, w):
        await mcp_server.run(r, w, mcp_server.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
```

### 2. Registrar o proxy no `openclaw.json` / `entrypoint.sh`

```json
"crm-proxy": {
  "command": "docker",
  "args": ["exec", "-i", "mcp-crm", "python3", "/app/proxy.py"],
  "type": "stdio"
}
```

No `entrypoint.sh` (reconcile function):
```js
config.mcp.servers["crm-proxy"] = {
  command: "docker",
  args: ["exec", "-i", "mcp-crm", "python3", "/app/proxy.py"],
  type: "stdio",
};
```

### 3. Trocar `mcp-crm` por `crm-proxy` nos agentes especializados

No `entrypoint.sh`, para cada agente que usa o MCP:
```js
tools: {
  allow: ["read", "crm-proxy"],
  deny: ["mcp-crm", ...],
},
```

### 4. Documentar as actions disponíveis no `AGENTS.md` de cada agente

O schema da tool genérica não lista parâmetros — isso vai no AGENTS.md:

```markdown
## CRM Tools
Sintaxe: `crm(action="<nome>", params={<campos>})`

| Action | Params obrigatórios |
|---|---|
| `search_contact` | `query` |
| `log_conversation_event` | `contact_id`, `direction`, `content_summary` |
```

Cada agente documenta **apenas as actions que ele usa** — o cold-contact tem 2, o orchestrator tem 5.

---

## Regras de schema para compatibilidade com OpenAI

Os modelos GPT-4.1 e GPT-5-nano rejeitam schemas com `anyOf`/`oneOf`/`allOf`/`not` no top level (`400 Invalid schema`).

**Antes (quebrado no GPT-4.1+):**
```python
inputSchema={
    "type": "object",
    "properties": {"nome": ..., "email": ..., "whatsapp": ...},
    "required": ["nome"],
    "anyOf": [{"required": ["email"]}, {"required": ["whatsapp"]}],  # ← QUEBRA
}
```

**Depois (compatível):**
```python
inputSchema={
    "type": "object",
    "properties": {"nome": ..., "email": ..., "whatsapp": ...},
    "required": ["nome"],
    # Regra de validação movida para description da tool
}
```

Mova a restrição para o campo `description`:
```python
description="Adiciona contato. Obrigatório: nome + ao menos um de: email, whatsapp ou telefone."
```

---

## Outras estratégias de redução (sem proxy)

### `skills: []` + `skillsLimits`
Remove a lista de skills globais do system prompt (~8.4k chars):
```json
{
  "id": "zind-crm-cold-contact",
  "skills": [],
  "skillsLimits": { "maxSkillsPromptChars": 0 }
}
```

### Sub-agentes já ganham redução automática
Agentes invocados via `sessions_send` (depth ≥ 1) recebem prompt "minimal" automaticamente:
- Omite: Skills, Model Aliases, User Identity, Reply Tags, Heartbeats
- Bootstrap: apenas `AGENTS.md` + `TOOLS.md` (não SOUL.md, IDENTITY.md, etc.)

**Consequência:** mover guardrails críticos de identidade (`display_name`, `company_guardrail`) para dentro do `AGENTS.md`, não no `IDENTITY.md`.

### `contextInjection: "continuation-skip"` (quando disponível)
Evita re-injetar o system prompt em turnos de continuação. Reduz custo em conversas multi-turno. Ver issue #76046 em https://github.com/openclaw/openclaw/issues/76046.

---

## Checklist ao criar/modificar um MCP

- [ ] MCP tem ≥ 5 tools? → criar `proxy.py`
- [ ] Schemas têm `anyOf`/`oneOf` no top level? → mover para `description`
- [ ] Agentes especializados têm `skills: []`?
- [ ] `AGENTS.md` de cada agente documenta as actions disponíveis?
- [ ] `mcp-original` está no `deny` dos agentes que usam o proxy?
- [ ] `bundle-tools` nos logs abaixo de 10s após a mudança?

---

## Implementação de referência

- Proxy: [mcps/crm_mcp/proxy.py](../mcps/crm_mcp/proxy.py)
- Agente usando proxy: [agents/zind-crm-cold-contact/AGENTS.md](../agents/zind-crm-cold-contact/AGENTS.md)
- Configuração: [entrypoint.sh](../entrypoint.sh) — seção `crm-proxy` e `desiredAgents`

---

## Lições operacionais (evitar incidentes)

### 1. Não allowlistar ações internas de tool (`sindico_leads`, `execute_lead_skill`)

Em `agents.list[].tools.allow`, o runtime espera IDs de tools registradas (core/plugin/MCP server), não nomes de `action` internos da tool proxy.

- **Errado:** `allow: ["sindico_leads", "execute_lead_skill"]`
- **Certo:** permitir o servidor MCP/proxy (ou usar política por `deny` quando houver instabilidade de resolução de allowlist dinâmica)

Sintoma típico no log:
- `agents.<agent>.tools.allow allowlist contains unknown entries (...)`

### 2. Proxy MCP + allowlist restritiva exige validação de registro real

Se o agente usar allowlist estrita, valide no boot que o proxy está de fato registrado e acessível; senão a tool fica invisível para o agente.

Checklist rápido:
- `mcp.servers["<proxy-id>"]` configurado com `type: "stdio"`
- comando do proxy funcional (`docker exec -i <container> python3 /app/proxy.py`)
- sem erro de handshake/timeout nos logs de `bundle-mcp`

### 3. Config persistida do gateway pode divergir do repositório

Mesmo com patch no repo, o arquivo persistido em `/root/.openclaw/openclaw.json` pode manter estado antigo.

Boas práticas:
- após mudanças de `agents.list`/crons, reiniciar `openclaw-gateway`
- confirmar `cron list` e logs pós-restart
- em incidente, inspecionar explicitamente a config persistida dentro do container

### 4. Cron IDs mudam quando o job é recriado

Depois de `recreate`, IDs antigos retornam `unknown cron job id`. Sempre usar o ID atual de `cron list` antes de `cron run`.

### 5. Critério de aceite para correção em produção

Considerar corrigido apenas quando:
- `openclaw infer model run --model usage-router/deepseek/deepseek-v4-pro ...` retorna `ok: true`
- cron de leads executa com `status: ok`
- logs sem `allowlist contains unknown entries` para o agente de leads
