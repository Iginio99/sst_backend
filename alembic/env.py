from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
import os
import sys

# ---- IMPORTANTE: agregar la ruta de tu app ----
# Esto permite que Alembic importe tus módulos
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Configuración alembic.ini
config = context.config

# Logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---- Importar tu metadata (Base) ----
from app.config.database import Base
from app.config.settings import settings

config.set_main_option("sqlalchemy.url", settings.DATABASE_URL.replace("%", "%%"))

# Esto permite autogenerate detectar tus modelos
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Ejecuta migraciones en modo OFFLINE (sin conexión activa).
    """
    url = config.get_main_option("sqlalchemy.url")
    
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Ejecuta migraciones en modo ONLINE (con conexión activa).
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
