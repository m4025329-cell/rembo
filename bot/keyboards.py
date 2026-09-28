"""Reply/Inline клавиатуры для бота."""
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    WebAppInfo,
)

from config import settings


def webapp_kb(url: str) -> InlineKeyboardMarkup:
    """
    Расширенная клавиатура /start, когда мини-приложение опубликовано.
    Первая кнопка открывает WebApp, ниже — быстрые ссылки на разделы.
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🖤 Открыть BlackLotusVPN",
            web_app=WebAppInfo(url=url),
        )],
        [
            InlineKeyboardButton(text="💳 Тарифы",    callback_data="menu:plans"),
            InlineKeyboardButton(text="🔑 Мой доступ", callback_data="menu:access"),
        ],
        [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="menu:help")],
    ])


def main_kb() -> InlineKeyboardMarkup:
    """
    Fallback-клавиатура, если WEBAPP_URL ещё не настроен (или равен
    плейсхолдеру example.com). WebApp-кнопки нет.
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💳 Тарифы",     callback_data="menu:plans"),
            InlineKeyboardButton(text="🔑 Мой доступ",  callback_data="menu:access"),
        ],
        [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="menu:help")],
    ])


def main_menu_kb() -> InlineKeyboardMarkup:
    """
    Обратно совместимый alias: возвращает webapp_kb при заданном
    WEBAPP_URL, иначе main_kb.
    """
    if settings.has_real_webapp:
        return webapp_kb(settings.WEBAPP_URL)
    return main_kb()


def access_menu_kb(has_active_sub: bool) -> InlineKeyboardMarkup:
    """
    Меню раздела «Мой доступ». Если подписка активна — показываем
    кнопку добавления дополнительного устройства.
    """
    rows = [
        [InlineKeyboardButton(
            text="🖤 Открыть BlackLotusVPN",
            web_app=WebAppInfo(url=settings.WEBAPP_URL),
        )]
    ]
    if has_active_sub:
        rows.append([
            InlineKeyboardButton(text="➕ Доп. устройство",
                                 callback_data="add_device")
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def add_device_kb() -> InlineKeyboardMarkup:
    """Заглушка кнопки оплаты доп. устройства."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить", callback_data="pay_device")]
    ])


def admin_menu_kb() -> InlineKeyboardMarkup:
    """Меню админа."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Статистика", callback_data="admin:stats")],
            [InlineKeyboardButton(text="📣 Рассылка", callback_data="admin:broadcast")],
            [InlineKeyboardButton(text="🎫 Выдать подписку", callback_data="admin:grant")],
            [InlineKeyboardButton(text="🚫 Отозвать подписку", callback_data="admin:revoke")],
        ]
    )
