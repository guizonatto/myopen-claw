# Regras de Atomicidade — OpenClaw

Cada componente do OpenClaw deve ser **atômico** e **autossuficiente**.

## O que significa atômico

- Faz **uma única coisa** — sem responsabilidades misturadas.
- Pode ser **executado isoladamente** sem depender de outros componentes do mesmo layer.
- Pode ser **testado isoladamente** sem precisar subir o sistema inteiro.

## O que significa autossuficiente

- Declara explicitamente seus **requisitos** no topo do arquivo (env vars, tabelas DB).
- Não tem estado oculto — toda configuração vem de `os.environ.get()`.
- Tem **ponto de entrada próprio** via `if __name__ == "__main__": run()`.

---

## Regras por camada

### Skill (`skills/`)

| Regra | Detalhe |
|---|---|
| Função obrigatória | `run()` — sem argumentos obrigatórios |
| Retorno | Dado processado (dict, list, str) — nunca `None` sem motivo |
| Proibido importar | Outra skill |
| Proibido fazer | Envio de notificação, HTTP externo (isso é tool) |
| Deve ter | `if __name__ == "__main__": print(run())` |
| Deve ter | Header `ENV_VARS` e `DB_TABLES` declarados (veja template) |

### Tool (`tools/`)

| Regra | Detalhe |
|---|---|
| Função obrigatória | `send(message)` para notificações, `fetch(url)` para scrapers |
| Proibido importar | Outra tool |
| Proibido fazer | Lógica de negócio, transformação de dados |
| Deve ter | `if __name__ == "__main__"` com exemplo mínimo |
| Deve ter | Header `ENV_VARS` declarados |

### Pipe (`pipes/`)

| Regra | Detalhe |
|---|---|
| Função obrigatória | `run()` |
| Pode importar | Skills + Tools + DB |
| Proibido | Lógica de negócio própria (delegar para skill) |
| Proibido | Agendar (isso é cron) ou escutar evento (isso é trigger) |
| Deve ter | `if __name__ == "__main__": run()` |

### Cron (`crons/`)

| Regra | Detalhe |
|---|---|
| Responsabilidade única | Agendar UM pipe |
| Proibido | Lógica de negócio ou orquestração própria |
| Estrutura | Um cron por pipe/processo |

### Trigger (`triggers/`)

| Regra | Detalhe |
|---|---|
| Responsabilidade | Escutar UM canal (HTTP, Telegram, etc.) |
| Rotas | Registrar apenas pipes em `PIPE_ROUTES` / `COMMAND_ROUTES` |
| Proibido | Processar dados diretamente |

### Agent (`agents/`)

| Regra | Detalhe |
|---|---|
| Responsabilidade | Lógica condicional entre pipes |
| Deve herdar | `BaseAgent` |
| Proibido | Chamar skills/tools diretamente (usar pipes) |

---

## Header obrigatório em todo componente

```python
"""
{Tipo}: {nome_arquivo}
Função: {o que faz em uma linha}
Usar quando: {contexto de uso}

ENV_VARS:
  - VAR_NOME: descrição do que é

DB_TABLES:
  - nome_tabela: leitura | escrita | leitura+escrita
"""
```

Se o componente não usa env vars ou DB, deixar `(nenhuma)`.

---

## Anti-padrões proibidos

```
# ERRADO — skill importando skill
from skills.twitter_trends import run as fetch_trends   ← PROIBIDO

# CERTO — pipe compondo skills
from skills.twitter_trends import run as fetch_trends   ← só em pipes/
```

```
# ERRADO — cron com lógica própria
@scheduler.scheduled_job(...)
def job():
    data = fetch_twitter()     ← lógica de negócio no cron
    send_telegram(data)

# CERTO — cron só agenda um pipe
@scheduler.scheduled_job(...)
def job():
    run()   ← pipe faz todo o trabalho
```

```
# ERRADO — hardcode
TELEGRAM_TOKEN = "123456:ABC"   ← NUNCA

# CERTO
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
```

---

## Crescimento por domínio

Enquanto um domínio tiver até **2 skills**, mantê-las no flat `skills/`.
A partir de **3 skills do mesmo domínio**, criar subdiretório:

```
skills/
  twitter/
    __init__.py
    trends.py       ← era skills/twitter_trends.py
    trends_browser.py
    summarize.py
  linkedin/
    __init__.py
    fetch.py
    summarize.py
```

Ao mover, atualizar todos os imports nos pipes correspondentes.

---

## Checklist antes de criar um componente novo

- [ ] Qual layer? (skill / tool / pipe / cron / trigger / agent)
- [ ] Nome segue a convenção? (`{dominio}_{acao}.py`)
- [ ] Header completo com ENV_VARS e DB_TABLES?
- [ ] Tem `if __name__ == "__main__"`?
- [ ] Não cruza horizontalmente o layer? (skill→skill, tool→tool)
- [ ] Variáveis de ambiente adicionadas ao `.env.example`?
- [ ] Arquivo de teste criado em `tests/{layer}/test_{nome}.py`?

---

## Checklist antes de modificar um componente

- [ ] A mudança quebra a interface pública do componente? (`run()`, `send()`)
- [ ] Pipes que usam este componente precisam ser atualizados?
- [ ] Os testes ainda passam?

Veja também: [INDEX.md](INDEX.md)
