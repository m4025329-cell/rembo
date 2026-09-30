"""
Обработчики команд пользователя.
- /start   — приветствие и кнопка WebApp
- /help    — краткая справка
- /status  — статус подписки
- reply-меню (footer_kb/full_menu_kb) — LumaVPN-style нижняя панель
"""
from urllib.parse import quote

from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import settings
from db.database import AsyncSessionLocal
from db.repo import (
    BASE_PRICE,
    DEVICE_PRICE,
    PLANS,
    SERVERS,
    get_or_create_user,
    list_devices,
    remove_device,
)

from .keyboards import (
    access_menu_kb,
    add_device_kb,
    devices_list_kb,
    footer_kb,
    full_menu_kb,
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
    # Reply-клавиатура шлётся отдельным сообщением — Telegram не позволяет
    # совместить inline и reply reply_markup в одном сообщении.
    await message.answer("Быстрое меню снизу 👇", reply_markup=footer_kb())


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


# ------------------------- Reply-меню (footer_kb / full_menu_kb) -------------------------

@router.message(F.text == "☰ Меню")
async def text_menu(message: Message) -> None:
    """Развернуть компактную панель в полное reply-меню."""
    await message.answer("📋 <b>Полное меню</b>", reply_markup=full_menu_kb(),
                         parse_mode="HTML")


@router.message(F.text == "👤 Профиль")
async def text_profile(message: Message) -> None:
    """«Профиль» — тот же контент, что и /status."""
    await cmd_status(message)


@router.message(F.text.in_({f"🖤 {settings.SERVICE_NAME} ЛК", "🔌 Подключить VPN"}))
async def text_open_webapp(message: Message) -> None:
    """Открыть мини-приложение (кнопки ЛК / «Подключить VPN»)."""
    kb = webapp_kb(settings.WEBAPP_URL) if settings.has_real_webapp else main_kb()
    await message.answer(home_text(), reply_markup=kb, parse_mode="HTML")


@router.message(F.text == "➕ Докупить устройства")
async def text_add_device(message: Message) -> None:
    """Докупить доп. устройство — доступно только при активной подписке."""
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
    if not has_active:
        await message.answer(
            "❌ Нужна активная подписка.\nОткрой мини-приложение и выбери тариф."
        )
        return
    await message.answer(
        f"Доп. устройство: +{DEVICE_PRICE:.0f} ₽/мес.\n"
        "Оплата пока не подключена.",
        reply_markup=add_device_kb(),
    )


@router.message(F.text == "🗑 Удаление устройств")
async def text_remove_devices(message: Message) -> None:
    """Список доп. устройств пользователя с кнопкой удаления на каждом."""
    if message.from_user is None:
        return
    async with AsyncSessionLocal() as session:
        user = await get_or_create_user(
            session,
            tg_id=message.from_user.id,
            username=message.from_user.username,
            full_name=message.from_user.full_name,
        )
        devices = await list_devices(session, user)
    if not devices:
        await message.answer("У тебя нет доп. устройств.")
        return
    await message.answer(
        "🗑 Твои доп. устройства — нажми, чтобы удалить:",
        reply_markup=devices_list_kb(devices),
    )


@router.callback_query(F.data.startswith("del_device:"))
async def cb_delete_device(cb: CallbackQuery) -> None:
    """Удалить доп. устройство по инлайн-кнопке из списка."""
    slot_id = int(cb.data.split(":", 1)[1])
    async with AsyncSessionLocal() as session:
        user = await get_or_create_user(
            session,
            tg_id=cb.from_user.id,
            username=cb.from_user.username,
            full_name=cb.from_user.full_name,
        )
        removed = await remove_device(session, user, slot_id)
    if removed:
        await cb.answer("Устройство удалено")
        await cb.message.answer("✅ Устройство удалено.")
    else:
        await cb.answer("Устройство не найдено", show_alert=True)


@router.message(F.text == "🎁 Подарить подписку")
async def text_gift(message: Message) -> None:
    """Заглушка подарка подписки — как в мини-приложении."""
    await message.answer("🎁 Подарок скоро будет доступен.")


@router.message(F.text == "💸 Партнёрка")
async def text_partners(message: Message) -> None:
    """Реферальная ссылка и статистика (заглушка — как во вкладке «Партнёры»)."""
    if message.from_user is None:
        return
    me = await message.bot.get_me()
    link = f"https://t.me/{me.username}?start=ref_{message.from_user.id}"
    text = (
        "💸 <b>Партнёрская программа</b>\n\n"
        "35% с платежей приглашённых пользователей.\n\n"
        f"🔗 Твоя ссылка:\n<code>{link}</code>\n\n"
        "👥 Приглашено: 0\n"
        "✅ Активных: 0\n"
        "💰 Заработано: 0 ₽"
    )
    await message.answer(text, parse_mode="HTML", disable_web_page_preview=True)


@router.message(F.text == "📤 Поделиться подпиской")
async def text_share(message: Message) -> None:
    """Реферальная ссылка + кнопка «Переслать» через share-диалог Telegram."""
    if message.from_user is None:
        return
    me = await message.bot.get_me()
    link = f"https://t.me/{me.username}?start=ref_{message.from_user.id}"
    share_text = f"Заходи в {settings.SERVICE_NAME} 🖤"
    share_url = f"https://t.me/share/url?url={quote(link)}&text={quote(share_text)}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Переслать", url=share_url)]
    ])
    await message.answer(f"🔗 <code>{link}</code>", reply_markup=kb, parse_mode="HTML")


@router.message(F.text == "ℹ️ О сервисе")
async def text_about(message: Message) -> None:
    """Статичная информация о сервисе."""
    servers = ", ".join(f"{s['flag']} {s['name']}" for s in SERVERS)
    text = (
        f"ℹ️ <b>{settings.SERVICE_NAME}</b>\n\n"
        "Быстрый и приватный VPN-доступ без цензуры.\n"
        "Протокол VLESS + Reality, без логов.\n\n"
        f"🌍 Серверы: {servers}"
    )
    if settings.support_url:
        text += f"\n\n💬 Поддержка: {settings.support_url}"
    await message.answer(text, parse_mode="HTML", disable_web_page_preview=True)


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
