import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

from app.core.config import settings
from app.db.database import Base
from app.models import models_db  # Imperative that we import our DB Models explicitly here

# Read Alembic settings mapping internally 
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Expose strictly declared declarative metadata so alembic calculates schema changes!
target_metadata = Base.metadata

def do_run_migrations(connection):
    """Executes constraints natively on the generated SQL session object limits"""
    context.configure(
        connection=connection, 
        target_metadata=target_metadata,
        compare_type=True, # Critical so it spots Float to Int changes if made later.
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online():
    """ Configure asynchronous sqlalchemy bounds for mapping. """
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = settings.async_database_url
    
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()

# Start flow correctly mapping logic securely explicitly bounds limits limits natively 
asyncio.run(run_migrations_online())