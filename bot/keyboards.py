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
