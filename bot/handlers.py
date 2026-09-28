"""
Обработчики команд пользователя.
- /start   — приветствие и кнопка WebApp
- /help    — краткая справка
- /status  — статус подписки
"""
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import CallbackQuery, Message

from db.database import AsyncSessionLocal
from db.repo import BASE_PRICE, DEVICE_PRICE, get_or_create_user

from .keyboards import access_menu_kb, add_device_kb, main_menu_kb


router = Router(name="user")


def home_text() -> str:
    """Приветственный текст (используется в /start)."""
    return (
        f"🖤 <b>BlackLotusVPN</b> — от {BASE_PRICE:.0f} ₽/мес\n\n"
        "Быстрый и приватный VPN-доступ без цензуры.\n"
        "Открой мини-приложение, чтобы выбрать тариф и получить ключ."
    )


# Оставлено для обратной совместимости с прежними импортами.
WELCOME_TEXT = home_text()


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
    await message.answer(home_text(), reply_markup=main_menu_kb(),
                         parse_mode="HTML")


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
    """/status — раздел «Мой доступ» с кнопкой доп. устройства."""
    if message.from_user is None:
        return
    async with AsyncSessionLocal() as session:
        user = await get_or_create_user(
            session,
            tg_id=message.from_user.id,
            username=message.from_user.username,
            full_name=message.from_user.full_name,
        )
        has_active = bool(user.subscription and user.is_subscribed)
        if has_active:
            text = (
                f"✅ <b>Мой доступ</b>\n"
                f"Подписка активна · тариф: <b>{user.subscription.plan}</b>\n"
                f"Истекает: {user.subscription.expires_at:%d.%m.%Y}\n"
                f"Доп. устройство: +{DEVICE_PRICE:.0f} ₽/мес."
            )
        else:
            text = ("❌ Подписка не активна.\n"
                    "Открой мини-приложение и выбери тариф.")
    await message.answer(text, reply_markup=access_menu_kb(has_active),
                         parse_mode="HTML")


@router.callback_query(F.data == "add_device")
async def cb_add_device(cb: CallbackQuery) -> None:
    """Заглушка покупки дополнительного устройства."""
    await cb.message.answer(
        f"Доп. устройство: +{DEVICE_PRICE:.0f} ₽/мес.\n"
        "Оплата пока не подключена.",
        reply_markup=add_device_kb(),
    )
    await cb.answer()


@router.callback_query(F.data == "pay_device")
async def cb_pay_device(cb: CallbackQuery) -> None:
    """Заглушка платёжки — только уведомление, ничего не списывает."""
    await cb.answer("Оплата пока не подключена", show_alert=True)


@router.message(F.web_app_data)
async def on_webapp_data(message: Message) -> None:
    """
    Приём данных из мини-приложения через Telegram.WebApp.sendData().
    Пока используется только для отладки — реальные операции идут через FastAPI.
    """
    await message.answer(f"Получено из WebApp: <code>{message.web_app_data.data}</code>",
                         parse_mode="HTML")
