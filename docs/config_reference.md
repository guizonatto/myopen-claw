# Resumo da configuração avançada do OpenClaw (openclaw.json)

O arquivo `~/.openclaw/openclaw.json` (JSON5) controla todos os aspectos do gateway, agentes, canais, ferramentas, plugins, automações e segurança. Todos os campos são opcionais; valores não definidos usam defaults seguros.

## Principais blocos e exemplos
- **channels**: configura canais (Telegram, WhatsApp, Discord, etc.), políticas de DM/grupo, tokens, limites, comandos, multi-conta, etc.
- **agents**: define agentes, modelos, identidade, sandbox, heartbeat, compaction, pruning, subagentes, overrides por agente.
- **session**: escopo, resets, identidade cruzada, políticas de envio, armazenamento.
- **messages**: prefixos, reações, fila, debounce, TTS, limites de histórico.
- **tools**: perfis, allow/deny, grupos, políticas por provider/modelo, exec, web, media, agentToAgent, sessões, subagentes.
- **skills**: allowlist, diretórios extras, preferências de instalação, overrides por skill.
- **plugins**: enable/disable, allow/deny, paths, configs e envs por plugin.
- **browser**: perfis, políticas SSRF, headless, args extras.
- **ui**: identidade visual, avatar, cor.
- **gateway**: porta, autenticação, UI, trusted proxies, push, endpoints compatíveis.
- **hooks**: integrações (ex: Gmail), tokens, mapeamentos, presets.
- **cron**: jobs agendados, limites, webhooks.
- **env**: variáveis inline, shellEnv, substituição em strings.
- **secrets**: providers (env, file, exec), defaults, refs.
- **logging**: nível, arquivo, estilo, redactions.
- **wizard**: metadados do setup.
- **includes**: permite dividir config em múltiplos arquivos via `$include`.

## Destaques
- Suporte a multi-agente, multi-canal, multi-modelo, sandboxing, automação, plugins e extensões.
- Políticas de segurança e controle granular de acesso, ferramentas e credenciais.
- Configuração modular, expansível e auditável.

Para detalhes e exemplos completos, consulte: https://docs.openclaw.ai/gateway/configuration-reference

Veja também: [INDEX.md](INDEX.md)
