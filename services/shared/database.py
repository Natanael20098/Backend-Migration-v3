from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from typing import AsyncGenerator


class Base(DeclarativeBase):
    pass


def create_engine(database_url: str, service_name: str = "service"):
    """
    Create an async SQLAlchemy engine for a Supabase/PostgreSQL connection.
    Uses asyncpg with prepared_statement_cache_size=0 to satisfy Supabase
    transaction pooler requirements (equivalent to HikariCP prepareThreshold=0).
    """
    return create_async_engine(
        database_url,
        pool_size=3,
        max_overflow=2,
        echo=False,
        connect_args={
            "server_settings": {"application_name": service_name},
            "prepared_statement_cache_size": 0,
        },
    )


def create_session_factory(engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def get_db(session_factory: async_sessionmaker[AsyncSession]) -> AsyncGenerator[AsyncSession, None]:
    async with session_factory() as session:
        yield session
