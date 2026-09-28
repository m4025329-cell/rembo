"""
Точка входа Telegram-бота BlackLotusVPN.
Запуск: python -m bot.main
"""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import settings
from db.database import init_db

from .handlers import router as user_router
from .admin import router as admin_router


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("blacklotus.bot")


async def main() -> None:
    """Инициализация БД, запуск диспетчера с polling."""
    await init_db()

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Порядок важен: сначала админ-роутер (у него FSM),
    # затем пользовательский.
    dp.include_router(admin_router)
    dp.include_router(user_router)

    logger.info("🖤 BlackLotusVPN bot стартует...")
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
