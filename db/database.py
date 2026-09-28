"""
Инициализация асинхронного движка SQLAlchemy и session-factory.

Дополнительно:
- директория БД создаётся вне репозитория (db-data/);
- на SQLite-файл ставим chmod 600 (только владелец).
"""
import logging
import os
from pathlib import Path

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from config import settings
from db.models import Base


logger = logging.getLogger("blacklotus.db")

engine = create_async_engine(
    settings.async_database_url,
    echo=False,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


def _harden_sqlite_file() -> None:
    """Создать каталог БД и выставить права 600 на SQLite-файл."""
    path: Path | None = settings.sqlite_path
    if not path:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        try:
            os.chmod(path, 0o600)
        except PermissionError:
            logger.warning("Не удалось выставить 600 на %s", path)


async def init_db() -> None:
    """Создать таблицы (без Alembic — MVP) и защитить файл БД."""
    _harden_sqlite_file()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    _harden_sqlite_file()  # повторно, потому что файл только что создан


async def get_session() -> AsyncSession:
    """FastAPI dependency."""
    async with AsyncSessionLocal() as session:
        yield session
