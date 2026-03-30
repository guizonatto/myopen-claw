import sys
import os
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool, text
from alembic import context

# Configurações de log
config = context.config

db_url = os.environ.get("DATABASE_URL")
if db_url:
    config.set_main_option("sqlalchemy.url", db_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import do model
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from models import Base  # noqa: E402

target_metadata = Base.metadata

# --- CONFIGURAÇÃO ESPECÍFICA DESTA APP ---
SCHEMA_NAME = "memories_mcp"

def include_object(object, name, type_, reflected, compare_to):
    """
    Filtra os objetos para que o Alembic ignore tudo o que 
    não pertence ao schema 'memories_mcp'.
    """
    if type_ == "table":
        return object.schema == SCHEMA_NAME
    return True
# -----------------------------------------

def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        # Onde a tabela alembic_version será criada para este app
        version_table_schema=SCHEMA_NAME,
        include_schemas=True,
        include_object=include_object
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    # CREATE SCHEMA e CREATE EXTENSION precisam rodar em AUTOCOMMIT
    # para evitar UniqueViolation dentro de transação
    with connectable.execution_options(isolation_level="AUTOCOMMIT").connect() as setup_conn:
        setup_conn.execute(
            text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA_NAME}")
        )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            # Isolamento da tabela de versão
            version_table_schema=SCHEMA_NAME,
            include_schemas=True,
            include_object=include_object,
            transaction_per_migration=True
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()