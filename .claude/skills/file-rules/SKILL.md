---
name: file-rules
description: Regras de localização de arquivos do projeto OpenClaw. Carregada automaticamente para garantir que nenhum arquivo seja criado no lugar errado.
user-invocable: false
---

## Regras sempre ativas para criação de arquivos

Antes de criar qualquer arquivo `.py` neste projeto, verifique:

### Onde cada tipo vai

- Coleta ou transformação de dados → `skills/`
- Integração externa (envio de mensagem, scraping, API de terceiro) → `tools/`
- Orquestração de skills + tools → `pipes/`
- Agendamento por horário (APScheduler) → `crons/`
- Ativação por evento externo (webhook, bot, mensagem) → `triggers/`
- Lógica condicional entre pipes → `agents/`
- Utilitário interno reutilizável em múltiplos módulos → `openclaw/`
- Testes → `tests/{layer}/test_{nome}.py`

### Naming obrigatório

- `skills/`: `{dominio}_{acao}.py` → ex: `linkedin_fetch.py`
- `tools/`: `{canal}_notify.py` / `{canal}_scraper.py` → ex: `telegram_notify.py`
- `pipes/`: `{processo}_pipe.py` → ex: `linkedin_monitor_pipe.py`
- `crons/`: `{processo}_cron.py` → ex: `linkedin_monitor_cron.py`
- `triggers/`: `{canal}_trigger.py` → ex: `http_trigger.py`
- `agents/`: `{nome}_agent.py` → ex: `trends_agent.py`
- `tests/`: `test_{nome_do_componente}.py` → ex: `tests/skills/test_twitter_trends.py`

### Atomicidade obrigatória

Todo componente deve:
1. Ter **header docstring** com `ENV_VARS:` e `DB_TABLES:` declarados
2. Ter **`if __name__ == "__main__"`** para execução standalone
3. Expor interface pública clara: `run()` para skills/pipes/crons, `send()` para tools
4. **Não importar horizontalmente** — skill não importa skill, tool não importa tool

### Domínios dentro de skills/

- Até 2 skills do mesmo domínio → manter flat em `skills/`
- 3+ skills do mesmo domínio → subdiretório `skills/{dominio}/` com `__init__.py`

### Proibido

- Criar arquivos `.py` de lógica de negócio diretamente em `openclaw/`
- Criar código de notificação fora de `tools/`
- Colocar lógica de orquestração dentro de `crons/` ou `triggers/`
- Hardcodar credenciais, tokens ou IDs — sempre via `os.environ.get()`
- Criar nova variável de ambiente sem adicionar ao `.env.example`
- Criar componente sem arquivo de teste correspondente em `tests/`
- Skill importando outra skill
- Tool importando outra tool
