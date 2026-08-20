"""Alembic environment for both online (DB connection) and offline (SQL generation) modes.

Reads DATABASE_URL from env, falling back to alembic.ini. Uses sync psycopg driver
for migrations — the app runtime uses asyncpg separately.
"""

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from contract_review.db import Base
from contract_review.database import get_database_url

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override sqlalchemy.url from DATABASE_URL env if available
try:
    sync_url = get_database_url(async_mode=False)
    config.set_main_option("sqlalchemy.url", sync_url)
except RuntimeError:
    pass  # fall back to alembic.ini default

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Generate SQL without a DB connection."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live DB."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
