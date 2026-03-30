# Guia Prático: Alembic + SQLAlchemy em Containers Docker (OpenClaw)

## 1. Estrutura Recomendada
- Cada MCP deve ter sua própria pasta, Dockerfile e migrations Alembic.
- O contexto de build do Dockerfile deve ser o diretório do MCP.
- O entrypoint.sh de cada MCP deve rodar `alembic upgrade head` antes de iniciar o servidor.

## 2. Regras para Alembic + SQLAlchemy
- Toda migration Alembic deve conter no topo:
  ```python
  revision = 'xxxx'
  down_revision = None  # ou a hash anterior
  branch_labels = None
  depends_on = None
  ```
- Toda tabela SQLAlchemy deve ter pelo menos um campo com `primary_key=True`.
- Nunca use o nome `metadata` como campo em modelos.
- O alembic.ini deve conter as seções [loggers], [handlers], [formatters] e [alembic].
- Para logging Alembic, inclua:
  ```ini
  [loggers]
  keys = root,alembic
  [logger_root]
  level = WARN
  handlers = console
  [logger_alembic]
  level = INFO
  handlers = console
  qualname = alembic
  [handlers]
  keys = console
  [handler_console]
  class = StreamHandler
  args = (sys.stdout,)
  level = NOTSET
  formatter = default
  [formatters]
  keys = default
  [formatter_default]
  format = %(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s
  ```

## 3. Dockerfile e Entrypoint
- Use COPY entrypoint.sh /entrypoint.sh e garanta que o contexto de build está correto.
- No entrypoint.sh, rode:
  ```sh
  alembic upgrade head
  exec uvicorn main:app --host 0.0.0.0 --port 8000
  ```
- Instale dependências Python em virtualenv para evitar warnings do pip.

## 4. Dicas de Debug
- Se aparecer erro de PK: verifique se todos os modelos têm primary_key.
- Se aparecer erro de revision: verifique se as variáveis obrigatórias estão no topo da migration.
- Se aparecer erro de logging: confira as seções do alembic.ini.
- Sempre rode `docker compose build --no-cache` após corrigir arquivos de build/contexto.

## 5. Referências
- https://alembic.sqlalchemy.org/
- docs/architecture.md
- docs/openclaw-mcp.md

---
Este guia foi gerado a partir de problemas reais enfrentados ao subir containers MCP com Alembic + SQLAlchemy no OpenClaw.
