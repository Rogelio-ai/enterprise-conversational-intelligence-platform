from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings


class DatabaseManager:
    def __init__(self, settings: Settings) -> None:
        self.engine = create_async_engine(
            settings.async_database_url,
            pool_pre_ping=True,
            pool_recycle=300,
            pool_size=settings.mysql_pool_size,
            max_overflow=settings.mysql_max_overflow,
        )
        self.session_factory = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        async with self.session_factory() as database_session:
            try:
                yield database_session
            except Exception:
                await database_session.rollback()
                raise

    async def check_connection(self) -> None:
        async with self.engine.connect() as connection:
            await connection.execute(text('SELECT 1'))

    async def dispose(self) -> None:
        await self.engine.dispose()
