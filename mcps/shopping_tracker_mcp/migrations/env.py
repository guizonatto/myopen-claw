from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool, text # Import text para o schema
from alembic import context
import sys
import os

# Ajuste do path para encontrar o módulo 'db'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from db import models  # noqa

# Objeto de configuração do Alembic
config = context.config

# Injeção da URL do banco via variável de ambiente
db_url = os.environ.get("DATABASE_URL")
if db_url:
    config.set_main_option("sqlalchemy.url", db_url)

# Configuração de logs
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = models.Base.metadata

# --- CONFIGURAÇÃO DE ISOLAMENTO ---
SCHEMA_NAME = "shopping_tracker_mcp"

def include_object(object, name, type_, reflected, compare_to):
    """
    Filtro para garantir que o autogenerate ignore tabelas de outros schemas.
    """
    if type_ == "table":
        return object.schema == SCHEMA_NAME
    return True
# ----------------------------------

def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Isolamento da tabela de versão e do escopo
        version_table_schema=SCHEMA_NAME,
        include_schemas=True,
        include_object=include_object,
        compare_type=True  # Recomendado para detectar mudanças de tipo de coluna
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    # CREATE SCHEMA precisa rodar em AUTOCOMMIT
    with connectable.execution_options(isolation_level="AUTOCOMMIT").connect() as setup_conn:
        setup_conn.execute(
            text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA_NAME}")
        )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table_schema=SCHEMA_NAME,
            include_schemas=True,
            include_object=include_object,
            transaction_per_migration=True,
            compare_type=True
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()