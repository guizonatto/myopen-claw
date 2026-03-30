# OpenClaw — Building Plugins

> **Resumo:** Plugins expandem o OpenClaw com novos canais, providers, ferramentas, hooks, comandos e integrações. Podem ser publicados no ClawHub ou npm, sem necessidade de PR no repositório principal.

---

## Pré-requisitos
- Node >= 22
- Gerenciador de pacotes (npm ou pnpm)
- TypeScript (ESM)
- Para plugins in-repo: repositório clonado e `pnpm install`

---

## Tipos de plugin
- **Channel plugin:** conecta a plataformas de mensagem (Discord, IRC, etc.)
- **Provider plugin:** adiciona provider de modelo (LLM, proxy, endpoint custom)
- **Tool/hook plugin:** registra ferramentas, hooks, comandos, rotas HTTP

---

## Exemplo rápido: tool plugin

### 1. Crie o pacote e manifest
```jsonc
// package.json + openclaw.plugin.json
{
  "name": "@myorg/openclaw-my-plugin",
  "version": "1.0.0",
  "type": "module",
  "openclaw": { "extensions": ["./index.ts"] }
}
```

### 2. Entry point
```ts
import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";
import { Type } from "@sinclair/typebox";

export default definePluginEntry({
  id: "my-plugin",
  name: "My Plugin",
  description: "Adds a custom tool to OpenClaw",
  register(api) {
    api.registerTool({
      name: "my_tool",
      description: "Do a thing",
      parameters: Type.Object({ input: Type.String() }),
      async execute(_id, params) {
        return { content: [{ type: "text", text: `Got: ${params.input}` }] };
      },
    });
  },
});
```
- Use `defineChannelPluginEntry` para canais.

### 3. Teste e publique
- Externo: publique no ClawHub ou npm, instale com `openclaw plugins install <package>`
- In-repo: coloque na workspace de plugins, detectado automaticamente
- Teste: `pnpm test -- <bundled-plugin-root>/my-plugin/`

---

## Capacidades de plugin
- LLM, CLI backend, canais, TTS/STT, media, imagem, web search, agent tools, comandos, hooks, rotas HTTP, CLI
- Veja SDK Overview para API completa

---

## Hooks e guards
- `before_tool_call: { block: true }` — terminal, bloqueia handlers abaixo
- `before_tool_call: { requireApproval: true }` — pausa execução e pede aprovação
- `message_sending: { cancel: true }` — terminal, bloqueia handlers abaixo
- `/approve` cobre exec e plugin approvals

---

## Registrando agent tools
```ts
api.registerTool({
  name: "my_tool",
  description: "Do a thing",
  parameters: Type.Object({ input: Type.String() }),
  async execute(_id, params) {
    return { content: [{ type: "text", text: params.input }] };
  },
});
// Opcional (user opt-in):
api.registerTool(
  {
    name: "workflow_tool",
    description: "Run a workflow",
    parameters: Type.Object({ pipeline: Type.String() }),
    async execute(_id, params) {
      return { content: [{ type: "text", text: params.pipeline }] };
    },
  },
  { optional: true },
);
```
- Usuário ativa tools opcionais em config:
```jsonc
{
  "tools": { "allow": ["workflow_tool"] }
}
```
- Use `optional: true` para tools com side effects ou dependências extras

---

## Convenções de import
- Sempre use subpaths: `openclaw/plugin-sdk/<subpath>`
- Nunca importe seu próprio plugin via SDK path

---

## Checklist de submissão
- package.json com metadata openclaw
- openclaw.plugin.json válido
- Entry point correto
- Imports corretos
- Testes passam
- `pnpm check` passa (in-repo)

---

## Testes beta
- Siga releases beta no GitHub e X
- Teste plugin assim que sair beta
- Reporte blockers com label beta-blocker
- PRs de blockers devem ter fix(<plugin-id>): beta blocker - <resumo>

---

## Referências
- SDK Overview
- Channel Plugins
- Provider Plugins
- Entry Points