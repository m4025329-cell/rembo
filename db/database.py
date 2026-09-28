"""
Инициализация асинхронного движка SQLAlchemy и session-factory.
Также содержит миграцию create_all() для MVP (без Alembic).
"""
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from config import settings
from db.models import Base


# Асинхронный движок SQLAlchemy
engine = create_async_engine(
    settings.async_database_url,
    echo=False,
    future=True,
)

# Фабрика сессий — используется во всех местах, где нужен доступ к БД
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    """Создать все таблицы. Вызывается при старте бота и вебапа."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    """Dependency-функция для FastAPI: выдаёт сессию БД."""
    async with AsyncSessionLocal() as session:
        yield session
