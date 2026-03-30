# Decisões do Projeto OpenClaw

## 2026-03-29 — MCP como Model Context Protocol
- MCP significa sempre Model Context Protocol na documentação.
- Skills passam a ser arquivos texto (YAML/JSON/MD) que descrevem operações a serem roteadas para MCPs.
- Cada MCP é um serviço/container independente, exposto via HTTP/SSE, e reside em `mcp/`.
- Toda documentação, exemplos e regras devem refletir esse padrão.

Veja também: [INDEX.md](INDEX.md)

## 2026-03-28 — Bancos de dados separados por domínio
Três módulos independentes em openclaw/:
  memory_db.py   → contatos + relacionamentos + memórias pessoais
  trends_db.py   → trends de mercado (Twitter, LinkedIn, Google, manual)
  content_db.py  → sugestões de conteúdo (ciclo ideia → publicado)
Trends e content se relacionam entre si e com contatos via FK opcional.
Cada módulo inicializa suas tabelas ao ser importado.

## 2026-03-28 — MEMORY persistido no PostgreSQL + pgvector
Banco de dados principal é PostgreSQL com extensão pgvector.
Memória modelada com 4 tipos cognitivos (episodica, semantica, procedural, follow_up),
campos de entidade, categoria, importância, validade e embedding vetorial.
Busca semântica via pgvector quando embeddings disponíveis.
Ver schema completo em `configs/MEMORY.md`.

## 2026-03-28 — Estrutura de diretórios canonizada via CLAUDE.md
CLAUDE.md referencia docs canônicos com @-imports em vez de duplicar conteúdo.
Regras de localização de arquivos em `docs/architecture.md`.
Identidade do agente em `configs/IDENTITY.md`.
Skills do Claude Code em `.claude/skills/`.

## 2026-03-28 — Dockerfile corrigido para deploy replicável
Dockerfile copia todos os diretórios relevantes (pipes/, crons/, triggers/, agents/).
poetry.lock não é mais ignorado no .gitignore — necessário para build reproduzível.
docker-compose.yml carrega .env via env_file.

## 2026-03-28 — Watchtower para atualização automática
Servidor atualiza container automaticamente após push de nova imagem Docker.
Configurado em watchtower-compose.yml.

## 2026-03-28 — Atomicidade e autossuficiência como princípio central
Cada componente (skill, tool, pipe, cron, trigger, agent) deve ser atômico (faz uma coisa só)
e autossuficiente (roda standalone, declara suas dependências no header).
Regras completas em docs/atomic_rules.md.
Imports horizontais proibidos: skill não importa skill, tool não importa tool.
Domínios com 3+ skills migram para subdiretório skills/{dominio}/.
Testes em tests/{layer}/test_{nome}.py espelhando a estrutura do source.
