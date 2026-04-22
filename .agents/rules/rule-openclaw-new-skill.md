# ---
description: Regras para nova skill — OpenClaw
alwaysApply: model_decision
# ---

# Regras para Nova Skill — OpenClaw

> Consulte também: [docs/how-to-create-skills -in-openclaw.md](../../docs/how-to-create-skills%20-in-openclaw.md) e [docs/openclaw-mcp.md](../../docs/openclaw-mcp.md)

## Responsabilidade
- Skills são arquivos texto (YAML, JSON ou Markdown) que descrevem operações a serem executadas por um MCP (Model Context Protocol).
- Devem ser atômicas: uma responsabilidade clara, testável isoladamente.

## Estrutura
- Cada skill reside em `skills/` (ou subpasta por domínio). Sempre adicione a skill na pasta correta conforme o domínio.
- Após criar ou alterar uma skill, é obrigatório garantir que a pasta e os arquivos correspondentes estejam incluídos no `Dockerfile` para deploy correto no ambiente OpenClaw.
- No Dockerfile, cada arquivo de skill deve ser copiado para `/app/skills/` (ou subdiretório correspondente) dentro do container.
- Deve conter `SKILL.md` com instruções e metadados.
- Proibido importar skills entre si.

## Boas práticas
- Use README.md, exemplos e referências para documentação.
- Testes devem mockar dependências externas.

## Pós-deploy
- Após o deploy, valide se a skill está acessível e funcional no ambiente OpenClaw.
