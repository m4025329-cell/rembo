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
from security.logging_setup import setup_logging

from .admin import router as admin_router
from .handlers import router as user_router
from .security import AntiFloodMiddleware


setup_logging()
logger = logging.getLogger("blacklotus.bot")


async def _notify_admin_start(bot: Bot) -> None:
    """Отправить админу сигнал, что бот стартанул."""
    try:
        await bot.send_message(
            settings.ADMIN_ID,
            "🖤 BlackLotusVPN bot запущен.",
        )
    except Exception as e:
        logger.warning("Не смогли уведомить админа о старте: %s", e)


async def _notify_admin_error(bot: Bot, err: Exception) -> None:
    """Best-effort алерт админу о фатальной ошибке."""
    try:
        await bot.send_message(
            settings.ADMIN_ID,
            f"🚨 Бот упал: <code>{type(err).__name__}: {err}</code>",
            parse_mode="HTML",
        )
    except Exception:
        pass


async def main() -> None:
    await init_db()

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Anti-flood — на сообщения и колбэки
    flood = AntiFloodMiddleware()
    dp.message.middleware(flood)
    dp.callback_query.middleware(flood)

    # Порядок: сначала админ (FSM), затем пользовательский
    dp.include_router(admin_router)
    dp.include_router(user_router)

    logger.info("🖤 BlackLotusVPN bot стартует (prod=%s)...", settings.is_prod)
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await _notify_admin_start(bot)
        await dp.start_polling(bot)
    except Exception as e:
        logger.exception("Fatal: %s", e)
        await _notify_admin_error(bot, e)
        raise
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
