from collections.abc import AsyncGenerator
from alembic import command
from alembic.config import Config
from sqlalchemy import Connection
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from settings import DatabaseSettings

_database_url = DatabaseSettings().DATABASE_URL # pyright: ignore[reportCallIssue]
_engine = create_async_engine(_database_url)
_db = async_sessionmaker(bind=_engine, expire_on_commit=False)

async def create_session() -> AsyncGenerator[AsyncSession, None]:
    async with _db() as session:
        yield session

def run_upgrade(connection: Connection, config: Config):
    config.attributes["connection"] = connection
    command.upgrade(config, "head")

async def run_migrations():
    config = Config("alembic.ini")
    config.set_main_option('sqlalchemy.url', str(_engine.url))
    
    async with _engine.connect() as connection:
        await connection.run_sync(run_upgrade, config)
    
