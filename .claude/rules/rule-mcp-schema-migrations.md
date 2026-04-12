# ---
description: Regra para versionamento e deploy de schema em MCPs — OpenClaw
alwaysApply: true
# ---

# Regra para Versionamento e Deploy de Schema em MCPs (Model Context Protocol)

## Padrão obrigatório
- Toda alteração de schema (criação, alteração, remoção de tabelas/campos, tipos, defaults, constraints ou dados estruturais) de domínio deve ser feita via migration Alembic dentro do respectivo MCP, seguindo o padrão dos docs canônicos do projeto.
	- Sempre que alterar dados de banco de dados ou colunas, crie uma migration atômica e clara.
	- Se não houver doc canônico para o padrão de migration, crie um doc em `docs/` descrevendo o padrão adotado.
- Cada MCP deve manter sua pasta de migrations (ex: mcp/memories_mcp/migrations/), versionando cada mudança de schema.
- Cada MCP deve usar um banco de dados isolado (ou, no mínimo, schema isolado) e sua própria tabela alembic_version, garantindo versionamento e deploy totalmente independentes dos demais MCPs.
- O deploy do MCP deve rodar automaticamente as migrations Alembic ao subir o container (ex: via entrypoint.sh ou comando no Dockerfile).
- É proibido criar ou alterar schema de domínio via código Python procedural ou scripts SQL soltos fora do fluxo de migrations do MCP.
- O core OpenClaw nunca gerencia schema de domínio dos MCPs.

## Boas práticas
- Documente cada migration com mensagem clara e data.
- Use um banco de dados isolado por MCP sempre que possível.
- Teste migrations em ambiente de staging antes do deploy em produção.
- Scripts SQL avulsos só são permitidos para bootstrap inicial, nunca para alterações incrementais.

## Referências
- https://alembic.sqlalchemy.org/
- docs/openclaw-mcp.md
