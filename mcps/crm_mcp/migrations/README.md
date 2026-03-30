# Migrations Alembic — crm_mcp

- Use `alembic revision --autogenerate -m "mensagem"` para criar novas migrations.
- Rode `alembic upgrade head` no deploy/startup para aplicar as migrations.
- Configure a string de conexão em alembic.ini.

## Deploy automático

Garanta que o comando abaixo rode no entrypoint do container para aplicar as migrations automaticamente:

```
alembic upgrade head
```
