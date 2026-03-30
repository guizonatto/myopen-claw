import sys
import os
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool, text
from alembic import context

# Configurações de log
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# URL do banco via ambiente
db_url = os.environ.get("DATABASE_URL")
if db_url:
    config.set_main_option("sqlalchemy.url", db_url)

# Ajuste do path para importar modelos futuramente
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# --- CONFIGURAÇÃO DE ISOLAMENTO ---
SCHEMA_NAME = "trends_mcp"

# Quando você tiver modelos, importe o Base e use: target_metadata = Base.metadata
target_metadata = None 

def include_object(object, name, type_, reflected, compare_to):
    """
    Bloqueia qualquer interação com tabelas de outros schemas.
    """
    if type_ == "table":
        # Se o objeto não tiver schema definido ou for diferente do esperado, ignora
        return object.schema == SCHEMA_NAME
    return True
# ----------------------------------

def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        # Define o schema da tabela de versão
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

    with connectable.connect() as connection:
        # Cria o schema caso não exista
        connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA_NAME}"))
        connection.commit()

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
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