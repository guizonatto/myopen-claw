# ---
description: Regras para agentes — OpenClaw
alwaysApply: model_decision
# ---

# Regras para Agentes — OpenClaw

> Consulte também: [docs/architecture.md](../../docs/architecture.md)

## Responsabilidade
- Agentes orquestram pipes, aplicando lógica condicional e tomada de decisão.
- Devem ser atômicos: cada agente executa um papel claro e isolado.
- Não devem conter lógica de transformação de dados (isso é papel de skills/pipes).

## Estrutura
- Cada agente reside em `agents/`, podendo usar subpastas por domínio.
- Devem declarar dependências explícitas no topo do arquivo.
- Devem expor um ponto de entrada principal (`run()` ou classe principal).

## Configuração
- Parâmetros e identidade do agente são definidos em `configs/AGENTS.md` e `configs/IDENTITY.md`.
- Agentes podem ter configurações específicas em `.claude/agents/`.
- Para multiagente, cada agente pode ter sandbox, tools e credenciais isoladas (ver docs/config_reference.md).

## Atomicidade
- Proibido importar outros agentes diretamente.
- Cada agente deve ser testável e executável isoladamente.

