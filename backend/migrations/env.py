from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
from app.database import Base
from app.models import *  # Import all models


config = context.config


fileConfig(config.config_file_name)


target_metadata = Base.metadata


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    from app.config import settings
    
    # Convert asyncpg URL to psycopg2 for Alembic (sync operations)
    database_url = settings.DATABASE_URL
    if "asyncpg" in database_url:
        database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
    
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = database_url
    
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )
        
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()

