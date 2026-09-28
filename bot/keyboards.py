"""Reply/Inline клавиатуры для бота."""
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    WebAppInfo,
)

from config import settings


def main_menu_kb() -> InlineKeyboardMarkup:
    """
    Главная клавиатура /start.
    Одна кнопка — открытие мини-приложения BlackLotusVPN.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🖤 Открыть BlackLotusVPN",
                    web_app=WebAppInfo(url=settings.WEBAPP_URL),
                )
            ]
        ]
    )


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
