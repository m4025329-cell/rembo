"""
Единая точка запуска: параллельно поднимает бот и FastAPI-сервер.

Используется в docker-compose (сервис `app`) и локально:
    python run.py
"""
import asyncio
import logging

import uvicorn

from config import settings
from db.database import init_db
from bot.main import main as bot_main


async def run_web() -> None:
    """Поднять FastAPI на WEBAPP_PORT."""
    config = uvicorn.Config(
        "webapp.main:app",
        host="0.0.0.0",
        port=settings.WEBAPP_PORT,
        log_level="info",
    )
    server = uvicorn.Server(config)
    await server.serve()


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    await init_db()
    # Запускаем бот и веб параллельно
    await asyncio.gather(bot_main(), run_web())


if __name__ == "__main__":
    asyncio.run(main())
