"""
Обработчики команд пользователя.
- /start   — приветствие и кнопка WebApp
- /help    — краткая справка
- /status  — статус подписки
"""
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

from db.database import AsyncSessionLocal
from db.repo import get_or_create_user

from .keyboards import main_menu_kb


router = Router(name="user")


WELCOME_TEXT = (
    "🖤 <b>BlackLotusVPN</b> — тёмный цветок в мире свободного интернета.\n\n"
    "Здесь ты получишь быстрый и приватный VPN-доступ без цензуры.\n"
    "Открой мини-приложение, чтобы выбрать тариф и получить ключ."
)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """/start — сохраняем пользователя и открываем WebApp."""
    user = message.from_user
    if user is None:
        return
    async with AsyncSessionLocal() as session:
        await get_or_create_user(
            session,
            tg_id=user.id,
            username=user.username,
            full_name=user.full_name,
        )
    await message.answer(WELCOME_TEXT, reply_markup=main_menu_kb(), parse_mode="HTML")


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """/help — короткая инструкция."""
    await message.answer(
        "🕸 <b>Помощь</b>\n\n"
        "/start — открыть меню и мини-приложение\n"
        "/status — статус подписки\n"
        "Для настройки клиента Happ — раздел «Инструкция» в мини-приложении.",
        parse_mode="HTML",
    )


@router.message(Command("status"))
async def cmd_status(message: Message) -> None:
    """/status — отдаёт статус подписки текущего пользователя."""
    if message.from_user is None:
        return
    async with AsyncSessionLocal() as session:
        user = await get_or_create_user(
            session,
            tg_id=message.from_user.id,
            username=message.from_user.username,
            full_name=message.from_user.full_name,
        )
        if user.subscription and user.is_subscribed:
            text = (
                f"✅ Подписка активна\n"
                f"Тариф: {user.subscription.plan}\n"
                f"Истекает: {user.subscription.expires_at:%d.%m.%Y}"
            )
        else:
            text = "❌ Подписка не активна. Открой мини-приложение и выбери тариф."
    await message.answer(text)


@router.message(F.web_app_data)
async def on_webapp_data(message: Message) -> None:
    """
    Приём данных из мини-приложения через Telegram.WebApp.sendData().
    Пока используется только для отладки — реальные операции идут через FastAPI.
    """
    await message.answer(f"Получено из WebApp: <code>{message.web_app_data.data}</code>",
                         parse_mode="HTML")
