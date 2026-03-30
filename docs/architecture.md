# Arquitetura OpenClaw — Processos

Veja também: [INDEX.md](INDEX.md) — índice mestre da documentação.

## Fluxo de um processo

```
[Evento/Horário]
      │
 [Trigger / Cron]   ←── QUANDO rodar
      │
   [Pipe]           ←── COMO orquestrar
   /      \
[Skill]  [Tool]     ←── O QUE fazer
      │
[Memory DB]         ←── ONDE guardar
```

## Papéis de cada camada

| Camada     | Pasta        | Responsabilidade                                             |
|------------|--------------|--------------------------------------------------------------|
| **Skill**  | `skills/`    | Busca, transforma ou descreve operações a serem executadas por MCPs (Model Context Protocol). |
| **Tool**   | `tools/`     | Integra sistemas externos (notificação, scraping, APIs).     |
| **Pipe**   | `pipes/`     | Orquestra skills, tools e MCPs em um fluxo completo. Tem `run()`.  |
| **Cron**   | `crons/`     | Agenda pipes via APScheduler (tempo fixo).                   |
| **Trigger**| `triggers/`  | Dispara pipes por evento (webhook, comando, mensagem).       |
| **Agent**  | `agents/`    | Orquestra pipes com lógica condicional / tomada de decisão.  |
| **MCP**    | `mcp/`       | Model Context Protocol: executa operações de IA via HTTP/SSE, cada MCP é um serviço/container independente. |
| **Memory** | `openclaw/memory_db.py` | Persiste aprendizados e histórico no PostgreSQL. |

---

def run():
## Como criar um novo processo

### Passo 1 — Skill textual (define operação)

```yaml
# skills/meu_processo.yaml
operation: fetch_data
mcp: meu_mcp
params:
    filtro: "ativo"
```

### Passo 2 — MCP (Model Context Protocol)

O MCP é um serviço/container em `mcp/` que executa operações via HTTP/SSE.

Exemplo de endpoint:
POST /execute
{
    "operation": "fetch_data",
    "params": {"filtro": "ativo"}
}

### Passo 3 — Tool (se precisar de integração externa)

```python
# tools/meu_output.py
def send(message: str):
        ...  # enviar via API
```

### Passo 2 — Tool (se precisar de integração externa)

```python
# tools/meu_output.py
def send(message: str):
    ...  # enviar via API
```

### Passo 3 — Pipe (orquestração)

```python
# pipes/meu_processo_pipe.py
from skills import meu_processo
from tools import meu_output

def run():
    data = meu_processo.run()
    summary = format(data)
    meu_output.send(summary)
```

### Passo 4a — Cron (agendado)

```python
# crons/meu_processo_cron.py
from apscheduler.schedulers.blocking import BlockingScheduler
from pipes.meu_processo_pipe import run

scheduler = BlockingScheduler()

@scheduler.scheduled_job('cron', hour=9, minute=0)
def job():
    run()

if __name__ == '__main__':
    scheduler.start()
```

### Passo 4b — Trigger (por evento)

```python
# Em triggers/http_trigger.py, adicione à PIPE_ROUTES:
from pipes.meu_processo_pipe import run
PIPE_ROUTES["/meu-processo"] = run

# Ou em triggers/telegram_trigger.py:
COMMAND_ROUTES["/meu"] = run
```

### Passo 4c — Agent (com decisão)

```python
# agents/meu_agente.py
from agents.base_agent import BaseAgent

class MeuAgente(BaseAgent):
    name = "meu_agente"

    def decide_and_run(self):
        # lógica condicional
        if condicao:
            self.run_pipe("meu_processo_pipe")
        else:
            self.remember("info", "condição não atendida")

if __name__ == "__main__":
    MeuAgente().run()
```

---

## Convenção de nomes

| Tipo     | Padrão de nome                    | Exemplo                         |
|----------|-----------------------------------|---------------------------------|
| Skill    | `{dominio}_{acao}.py`             | `twitter_fetch.py`              |
| Tool     | `{canal}_notify.py` / `{canal}_scraper.py` | `telegram_notify.py`   |
| Pipe     | `{processo}_pipe.py`              | `trends_report_pipe.py`         |
| Cron     | `{processo}_cron.py`              | `trends_report_cron.py`         |
| Trigger  | `{canal}_trigger.py`              | `telegram_trigger.py`           |
| Agent    | `{nome}_agent.py`                 | `trends_agent.py`               |

---

## Exemplo: processo completo "LinkedIn Monitor"

```
skills/linkedin_fetch.py          ← busca posts via scraping
skills/linkedin_summarize.py      ← resume com NLP/LLM
tools/telegram_notify.py          ← envia resumo (já existe)
pipes/linkedin_monitor_pipe.py    ← orquestra fetch → summarize → notify
crons/linkedin_monitor_cron.py    ← roda diariamente às 7h
```

---

## Executar um processo manualmente

```sh
python -m pipes.meu_processo_pipe
python -m crons.meu_processo_cron
python -m agents.meu_agente
python -m triggers.http_trigger
python -m triggers.telegram_trigger
```
