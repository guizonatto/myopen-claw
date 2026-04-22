# ---
description: Regras de estilo de código — OpenClaw
alwaysApply: true
# ---
# Regras de Estilo de Código — OpenClaw

## Python
- Siga **PEP8** rigorosamente (use `black` para formatação automática).
- Use nomes descritivos e explícitos para variáveis, funções e classes.
- Funções públicas devem ter **docstrings** no padrão Google ou NumPy.
- Sempre declare dependências de ambiente e banco no topo do arquivo (`ENV_VARS`, `DB_TABLES`).
- Imports: padrão absoluto, exceto para submódulos do mesmo domínio.
- Proibido importar skills dentro de skills, tools dentro de tools (atomicidade).

## Organização de arquivos
- Skills, tools, pipes, crons e triggers devem estar em suas pastas específicas, podendo usar subdiretórios por domínio.
- Cada arquivo deve conter **uma única responsabilidade**.
- Scripts utilitários e exemplos vão para `scripts/` ou subpastas `examples/`.

## Boas práticas
- Prefira funções puras e side effects explícitos.
- Use type hints sempre que possível.
- Comentários devem explicar "por quê", não "o quê".
- Evite duplicação de código; extraia helpers para módulos utilitários.
