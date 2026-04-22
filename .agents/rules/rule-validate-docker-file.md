# ---
description: Regra para validar outputs no Dockerfile — OpenClaw
alwaysApply: model_decision
# ---

# Regra para Validação de Outputs no Dockerfile — OpenClaw

> Consulte também: [docs/architecture.md](../../docs/architecture.md)

## Objetivo
Garantir que o Dockerfile do projeto OpenClaw inclua todos os diretórios e arquivos necessários para o funcionamento correto em produção.

## O que validar
- O Dockerfile deve copiar explicitamente todos os diretórios de outputs do projeto, incluindo:
  - `skills/` (e subpastas)
  - `tools/`
  - `pipes/`
  - `crons/`
  - `triggers/`
  - `agents/`
  - `.claude/hooks/` (e outros scripts de automação)
  - `configs/` (parâmetros, identidade, heartbeat, etc.)
  - `workflows/` (se aplicável)
- Cada novo componente criado (skill, tool, pipe, cron, trigger, agent, hook) deve ser incluído no Dockerfile para garantir deploy correto.

## Como validar
- Sempre revise o Dockerfile após criar ou mover arquivos de outputs.
- Use scripts ou checklists para garantir que nenhum diretório/arquivo essencial ficou de fora.
- Em caso de dúvida, consulte a documentação em `docs/architecture.md` e `CLAUDE.md`.
- Sempre que alterar a estrutura de pastas (adicionar, mover, renomear ou remover diretórios relevantes), é OBRIGATÓRIO atualizar todos os Dockerfiles, docker-compose.yml e scripts de auto-update (ex: auto-updater.sh, mcp-updater.sh) para garantir que o OpenClaw reconheça e sincronize a nova estrutura automaticamente.

## Boas práticas
- Prefira COPYs explícitos para cada pasta relevante.
- Automatize a validação via CI/CD quando possível.
- Documente exceções ou exclusões intencionais no próprio Dockerfile.
