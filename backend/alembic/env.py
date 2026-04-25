from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# Import Base so target_metadata knows all ORM models
from app.models.models import Base
from app.core.config import settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override whatever alembic.ini says — read DATABASE_URL_SYNC from environment
config.set_main_option("sqlalchemy.url", settings.database_url_sync)

# target_metadata enables future alembic autogenerate (we hand-write Phase 1,
# but keeping this set correctly is required for downgrade + future migrations)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations without a live DB connection (generates SQL only)."""
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
    """Run migrations against live DB using psycopg2 sync engine."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
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
