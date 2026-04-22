# Uso de Schemas Isolados para Cada MCP no Postgres

- **Obrigatório:** Cada MCP deve definir e usar seu próprio schema no Postgres para garantir isolamento e atomicidade de domínio.
- No SQLAlchemy, defina o schema em cada modelo:
  ```python
  class Memory(Base):
      __tablename__ = 'memories'
      __table_args__ = {'schema': 'example_mcp'}
      # ... campos ...
  ```
  Ou defina o schema padrão para todos os modelos:
  ```python
  from sqlalchemy import MetaData
  Base = declarative_base(metadata=MetaData(schema='example_mcp'))
  ```
- O alembic.ini pode continuar apontando para o mesmo banco, mas as migrations criarão as tabelas no schema correto.
- Para bancos realmente separados, use DATABASE_URLs diferentes.
- O entrypoint.sh e o Dockerfile não mudam, apenas garanta que o schema existe (pode criar com um script SQL inicial).

**Resumo:**
- Cada MCP = 1 schema isolado no Postgres.
- Configure o schema nos modelos SQLAlchemy.
- Documente e valide no deploy.
