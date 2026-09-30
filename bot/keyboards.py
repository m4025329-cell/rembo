"""Reply/Inline клавиатуры для бота."""
import time

from typing import Sequence

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    WebAppInfo,
)

from config import settings

_BUILD = int(time.time())


def _v(url: str) -> str:
    """Добавить ?v=<время старта бота>: после рестарта Telegram не покажет кэш мини-аппа."""
    return f"{url}{'&' if '?' in url else '?'}v={_BUILD}"
from db.models import DeviceSlot


def webapp_kb(url: str) -> InlineKeyboardMarkup:
    """
    Расширенная клавиатура /start, когда мини-приложение опубликовано.
    Первая кнопка открывает WebApp, ниже — быстрые ссылки на разделы.
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🖤 Открыть BlackLotusVPN",
            web_app=WebAppInfo(url=_v(url)),
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
            web_app=WebAppInfo(url=_v(settings.WEBAPP_URL)),
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


def footer_kb() -> ReplyKeyboardMarkup:
    """
    Компактная persistent-клавиатура по умолчанию (как у LumaVPN):
    короткая полоска снизу с раскрытием в полное меню по «☰ Меню».
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="👤 Профиль"),
                KeyboardButton(text="💸 Партнёрка"),
                KeyboardButton(text="☰ Меню"),
            ],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def full_menu_kb() -> ReplyKeyboardMarkup:
    """Полное reply-меню — открывается кнопкой «☰ Меню» из footer_kb()."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=f"🖤 {settings.SERVICE_NAME} ЛК")],
            [KeyboardButton(text="🔌 Подключить VPN")],
            [KeyboardButton(text="➕ Докупить устройства")],
            [KeyboardButton(text="🗑 Удаление устройств")],
            [
                KeyboardButton(text="🎁 Подарить подписку"),
                KeyboardButton(text="💸 Партнёрка"),
            ],
            [KeyboardButton(text="📤 Поделиться подпиской")],
            [KeyboardButton(text="ℹ️ О сервисе")],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def devices_list_kb(devices: Sequence[DeviceSlot]) -> InlineKeyboardMarkup:
    """По кнопке на каждое доп. устройство — удалить."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🗑 {d.device_name}",
                              callback_data=f"del_device:{d.id}")]
        for d in devices
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
