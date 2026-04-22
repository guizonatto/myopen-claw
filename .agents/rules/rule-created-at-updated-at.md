# Regra para colunas created_at e updated_at em todos os MCPs

Sempre que adicionar as colunas `created_at` ou `updated_at` em models ou migrations, siga obrigatoriamente:

## Models (SQLAlchemy)
```python
created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
```

## Migrations (Alembic)
```python
sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
```

## SQL puro
```sql
created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
```

> Isso garante que o horário atual seja sempre preenchido automaticamente, tanto via ORM quanto via SQL direto, em todos os MCPs do OpenClaw.
