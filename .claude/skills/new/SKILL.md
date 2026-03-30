---
name: new
description: Cria um novo componente OpenClaw (skill, tool, pipe, cron, trigger, agent) no diretório correto, com naming convention e template certos. Use quando o usuário pedir para criar qualquer novo arquivo de código no projeto.
allowed-tools: [Write, Read, Glob]
---

O usuário quer criar: $ARGUMENTS

## Regras de localização

Determine o tipo de componente e crie o arquivo no lugar correto:

| Tipo | Pasta | Nome do arquivo |
|---|---|---|
| skill | `skills/` | `{dominio}_{acao}.py` |
| tool | `tools/` | `{canal}_notify.py` ou `{canal}_scraper.py` |
| pipe | `pipes/` | `{processo}_pipe.py` |
| cron | `crons/` | `{processo}_cron.py` |
| trigger | `triggers/` | `{canal}_trigger.py` |
| agent | `agents/` | `{nome}_agent.py` |

Se o usuário não especificou o tipo, infira pelo que ele descreveu:
- "buscar dados de X" → skill
- "enviar mensagem / notificar" → tool
- "rodar todo dia / toda semana" → cron
- "quando receber webhook / comando" → trigger
- "decidir qual processo rodar" → agent
- "conectar skill com tool" → pipe

## Regra de domínio (para skills)

- Até 2 skills do mesmo domínio → manter em `skills/` flat
- 3 ou mais skills do mesmo domínio → criar subdiretório `skills/{dominio}/` com `__init__.py`

## Templates obrigatórios

Todo componente deve ter:
1. **Header docstring** com Função, Usar quando, ENV_VARS, DB_TABLES
2. **`if __name__ == "__main__"`** para execução standalone
3. **Sem imports horizontais** — skill não importa skill, tool não importa tool

### Skill

```python
"""
Skill: {nome_arquivo}
Função: {o que faz em uma linha}
Usar quando: {contexto de uso}

ENV_VARS:
  - {VAR_NOME}: {descrição} (ou "(nenhuma)")

DB_TABLES:
  - {tabela}: leitura | escrita | leitura+escrita (ou "(nenhuma)")
"""
import os
from openclaw.db import get_connection


def run():
    """Executa a skill e retorna o resultado."""
    pass


if __name__ == "__main__":
    print(run())
```

### Tool

```python
"""
Tool: {nome_arquivo}
Função: {o que faz em uma linha}
Usar quando: {contexto de uso}

ENV_VARS:
  - {VAR_NOME}: {descrição}
"""
import os
import requests

{VAR_NOME} = os.environ.get("{ENV_VAR}", "")


def send(message: str) -> bool:
    """Envia a mensagem e retorna True se bem-sucedido."""
    pass


if __name__ == "__main__":
    send("teste de envio")
```

### Pipe

```python
"""
Pipe: {nome_arquivo}
Função: {o que faz em uma linha}
Usar quando: {contexto de uso}

Fluxo:
  {skill_name}.run() → {tool_name}.send()

ENV_VARS: (via skills e tools usadas)
"""
from skills.{skill_name} import run as {skill_alias}
from tools.{tool_name} import send as {tool_alias}


def run():
    data = {skill_alias}()
    {tool_alias}(str(data))


if __name__ == "__main__":
    run()
```

### Cron

```python
"""
Cron: {nome_arquivo}
Função: Agendar {processo} para rodar {frequencia}.
Executar: python -m crons.{nome}

ENV_VARS: (nenhuma — via pipe)
"""
from apscheduler.schedulers.blocking import BlockingScheduler
from pipes.{pipe_name} import run

scheduler = BlockingScheduler()


@scheduler.scheduled_job('cron', hour={hora}, minute=0)
def job():
    print('Executando {processo}...')
    run()


if __name__ == '__main__':
    print('Iniciando {processo}...')
    scheduler.start()
```

### Trigger

```python
"""
Trigger: {canal}_trigger.py
Função: Disparar pipes via {canal}.
Executar: python -m triggers.{canal}_trigger

ENV_VARS:
  - {TOKEN_VAR}: token de autenticação do canal
"""
# Registre pipes em PIPE_ROUTES (http_trigger) ou COMMAND_ROUTES (telegram_trigger)
# Não processe dados diretamente aqui — delegue para pipes.
```

### Agent

```python
"""
Agent: {nome_arquivo}
Função: {o que decide em uma linha}
Executar: python -m agents.{nome}

ENV_VARS: (nenhuma — via pipes)
"""
from agents.base_agent import BaseAgent


class {NomeAgent}(BaseAgent):
    name = "{nome}"

    def decide_and_run(self):
        # implemente a lógica condicional aqui
        # use self.run_pipe("nome_pipe") para executar
        # use self.remember("tipo", "conteudo") para salvar no MEMORY
        pass


if __name__ == "__main__":
    {NomeAgent}().run()
```

## Após criar o arquivo

1. Verificar se alguma variável de ambiente nova deve ser adicionada ao `.env.example`.
2. Criar arquivo de teste em `tests/{layer}/test_{nome}.py`.
3. Avisar o usuário o caminho exato do arquivo criado.
4. Se for um novo processo completo (skill + pipe + cron/trigger), perguntar se deseja criar todos os componentes.
