# Obrigatoriedade de Migration Alembic em MCPs

- Todo MCP deve conter pelo menos uma migration Alembic inicial para criar as tabelas do domínio.
- O arquivo de migration deve estar em `migrations/versions/` e conter as variáveis obrigatórias no topo (`revision`, `down_revision`, etc).
- O comando para gerar a migration inicial é:
  ```sh
  alembic revision --autogenerate -m "initial"
  ```
- As migrations são aplicadas automaticamente no banco de dados pelo entrypoint.sh do container, que executa:
  ```sh
  alembic upgrade head
  exec uvicorn main:app --host 0.0.0.0 --port 8000
  ```
- O Dockerfile apenas garante que o entrypoint.sh está presente e executável.

**Resumo:** Sem migration, o banco não é criado. O Alembic + entrypoint.sh garantem a criação e versionamento do schema ao subir o container.
