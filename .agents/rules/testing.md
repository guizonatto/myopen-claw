# ---
description: Regras de testes — OpenClaw
alwaysApply: model_decision
# ---
# Regras de Testes — OpenClaw

## Princípios Gerais
- Todo componente (skill, tool, pipe, cron, trigger, agent) deve ser **testável isoladamente** (atomicidade).
- Testes devem cobrir casos de sucesso, falha e borda.
- Cobertura mínima de 80% (preferencialmente reportada via pytest-cov).

## Framework
- Use **pytest** como framework principal.
- Testes devem rodar via `pytest` na raiz do projeto.

## Estrutura
- Cada módulo deve ter um arquivo de teste correspondente em `tests/` (ex: `skills/foo.py` → `tests/skills/test_foo.py`).
- Testes de pipes, crons e triggers devem simular eventos e entradas reais.
- Skills e tools devem ser testados sem dependências externas (mock de APIs, DB, env vars).

## Atomicidade
- Testes não devem depender de ordem de execução.
- Cada teste deve ser independente e restaurar o ambiente ao final.

## Boas práticas
- Use fixtures para setup/teardown.
- Prefira asserts explícitos e mensagens claras de erro.
- Testes lentos ou que dependem de recursos externos devem ser marcados com `@pytest.mark.slow` ou `@pytest.mark.external`.
