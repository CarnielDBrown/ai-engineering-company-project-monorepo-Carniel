"""Alembic environment for explicit SQLModel/PostgreSQL schema migrations."""

from logging.config import fileConfig
import os
from pathlib import Path
import sys

from sqlalchemy import create_engine
from sqlalchemy import pool
from sqlalchemy.engine import URL, make_url

from alembic import context
from sqlmodel import SQLModel

# Add the service root to imports when Alembic is invoked from another cwd
# (for example, from the installed console script).
service_root = str(Path(__file__).resolve().parents[1])
if service_root not in sys.path:
    sys.path.insert(0, service_root)

import models  # noqa: F401 -- registers inventory tables with SQLModel.metadata

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def _database_url() -> URL:
    """Load and validate an explicit PostgreSQL URL without logging credentials."""
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL must be set explicitly to run Alembic migrations")

    parsed = make_url(url)
    if parsed.get_backend_name() != "postgresql":
        raise RuntimeError("Alembic migrations are supported only for PostgreSQL")
    if parsed.drivername == "postgresql":
        parsed = parsed.set(drivername="postgresql+psycopg2")
    return parsed

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = _database_url()
    context.configure(
        url=url.render_as_string(hide_password=True),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = create_engine(_database_url(), poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
