"""
Обработчики команд пользователя.
- /start   — приветствие и кнопка WebApp
- /help    — краткая справка
- /status  — статус подписки
"""
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import CallbackQuery, Message

from config import settings
from db.database import AsyncSessionLocal
from db.repo import BASE_PRICE, DEVICE_PRICE, PLANS, get_or_create_user

from .keyboards import (
    access_menu_kb,
    add_device_kb,
    main_kb,
    webapp_kb,
)


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
    """/start — регистрация нового пользователя или welcome back."""
    user = message.from_user
    if user is None:
        return
    async with AsyncSessionLocal() as session:
        db_user = await get_or_create_user(
            session,
            tg_id=user.id,
            username=user.username,
            full_name=user.full_name,
        )
        is_new = getattr(db_user, "_is_new", False)

    kb = webapp_kb(settings.WEBAPP_URL) if settings.has_real_webapp else main_kb()

    if is_new:
        text = (
            f"✅ <b>Регистрация прошла!</b>\n\n"
            f"Привет, {user.first_name}! Добро пожаловать в "
            f"<b>{settings.SERVICE_NAME}</b>.\n\n"
            f"Открой мини-приложение, чтобы выбрать тариф "
            f"и получить VPN-ключ."
        )
    else:
        text = home_text()

    await message.answer(text, reply_markup=kb, parse_mode="HTML")


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


@router.callback_query(F.data == "menu:plans")
async def cb_menu_plans(cb: CallbackQuery) -> None:
    """Показать список тарифов в чате (без открытия WebApp)."""
    lines = [f"💳 <b>Тарифы {settings.SERVICE_NAME}</b>\n"]
    for _, p in PLANS.items():
        lines.append(f"• {p['title']} — <b>{p['price']:.0f} ₽</b>")
    lines.append(f"\n➕ Доп. устройство: +{DEVICE_PRICE:.0f} ₽/мес")
    await cb.message.answer("\n".join(lines), parse_mode="HTML")
    await cb.answer()


@router.callback_query(F.data == "menu:access")
async def cb_menu_access(cb: CallbackQuery) -> None:
    """Показать статус доступа (аналог /status, но по кнопке)."""
    async with AsyncSessionLocal() as session:
        user = await get_or_create_user(
            session,
            tg_id=cb.from_user.id,
            username=cb.from_user.username,
            full_name=cb.from_user.full_name,
        )
        has_active = bool(user.subscription and user.is_subscribed)
        if has_active:
            text = (
                f"✅ <b>Мой доступ</b>\n"
                f"Тариф: <b>{user.subscription.plan}</b>\n"
                f"Истекает: {user.subscription.expires_at:%d.%m.%Y}"
            )
        else:
            text = "❌ Подписка не активна. Выбери тариф во вкладке «Тарифы»."
    await cb.message.answer(text, reply_markup=access_menu_kb(has_active),
                            parse_mode="HTML")
    await cb.answer()


@router.callback_query(F.data == "menu:help")
async def cb_menu_help(cb: CallbackQuery) -> None:
    """Показать краткую справку и ссылку на поддержку."""
    text = (
        "ℹ️ <b>Помощь</b>\n\n"
        "• /start — открыть меню\n"
        "• /status — статус подписки\n"
        "• Инструкция по Happ — в мини-приложении\n"
    )
    if settings.support_url:
        text += f"\n💬 Поддержка: {settings.support_url}"
    await cb.message.answer(text, parse_mode="HTML",
                            disable_web_page_preview=True)
    await cb.answer()


@router.message(F.web_app_data)
async def on_webapp_data(message: Message) -> None:
    """
    Приём данных из мини-приложения через Telegram.WebApp.sendData().
    Пока используется только для отладки — реальные операции идут через FastAPI.
    """
    await message.answer(f"Получено из WebApp: <code>{message.web_app_data.data}</code>",
                         parse_mode="HTML")
