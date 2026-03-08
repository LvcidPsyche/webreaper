"""
Alembic migration environment.
Reads DATABASE_URL from the environment — never hardcoded.
"""
import asyncio
import os
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# ---------------------------------------------------------------------------
# Alembic Config object (access to alembic.ini values)
# ---------------------------------------------------------------------------
config = context.config

# Wire up DATABASE_URL from environment — required.
database_url = os.environ.get("DATABASE_URL")
if not database_url:
    raise RuntimeError(
        "DATABASE_URL environment variable is not set.\n"
        "Example: export DATABASE_URL=sqlite+aiosqlite:///~/.webreaper/webreaper.db\n"
        "Then run: alembic upgrade head"
    )
config.set_main_option("sqlalchemy.url", database_url)

# Set up logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---------------------------------------------------------------------------
# Import models so autogenerate can detect schema changes.
#
# This import must pull in every SQLAlchemy model that inherits from Base.
# If you add new model files, make sure they are imported here (or via
# webreaper.models.__init__).
# ---------------------------------------------------------------------------
try:
    from webreaper.database import Base
    # Importing models ensures they register on Base.metadata
    import webreaper.models  # noqa: F401
    target_metadata = Base.metadata
except ImportError:
    # Fallback: if models aren't wired up yet, autogenerate will be empty
    # but manual migrations still work.
    target_metadata = None


# ---------------------------------------------------------------------------
# Offline migrations (generates SQL without a live DB connection)
# ---------------------------------------------------------------------------
def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Online migrations (runs against a live DB connection)
# ---------------------------------------------------------------------------
def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
