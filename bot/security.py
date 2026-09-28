"""
Секьюрити-слой для aiogram:
- декоратор admin_only,
- middleware anti-flood (не более N сообщений/сек от одного user_id).
"""
import time
from collections import defaultdict, deque
from functools import wraps
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from config import settings
from security.logging_setup import audit


def is_admin(user_id: int | None) -> bool:
    return user_id is not None and user_id == settings.ADMIN_ID


def admin_only(handler):
    """
    Декоратор для aiogram-хэндлеров: пропускает только ADMIN_ID.
    Работает для Message и CallbackQuery. Логирует попытки в audit.log.
    """
    @wraps(handler)
    async def wrapper(event, *args, **kwargs):
        user = getattr(event, "from_user", None)
        uid = getattr(user, "id", None)
        if not is_admin(uid):
            audit(uid or 0, "admin_denied", handler=handler.__name__)
            if isinstance(event, CallbackQuery):
                await event.answer("Нет доступа", show_alert=True)
            # для обычных сообщений просто молчим — не палим админку
            return
        return await handler(event, *args, **kwargs)
    return wrapper


class AntiFloodMiddleware(BaseMiddleware):
    """
    Ограничивает частоту сообщений от одного пользователя.
    В памяти держим короткое окно последних событий на юзера.
    """

    def __init__(self, limit_per_second: int | None = None) -> None:
        self.limit = limit_per_second or settings.BOT_FLOOD_LIMIT_PER_SECOND
        self._buckets: Dict[int, deque[float]] = defaultdict(deque)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user = getattr(event, "from_user", None)
        uid = getattr(user, "id", None)
        if uid is None:
            return await handler(event, data)

        now = time.monotonic()
        bucket = self._buckets[uid]
        # Оставляем только события за последнюю секунду
        while bucket and now - bucket[0] > 1.0:
            bucket.popleft()

        if len(bucket) >= self.limit:
            # Мягко отвечаем и не пускаем в хендлер
            if isinstance(event, Message):
                try:
                    await event.answer("⏳ Слишком часто. Подожди секунду.")
                except Exception:
                    pass
            elif isinstance(event, CallbackQuery):
                try:
                    await event.answer("Слишком часто", show_alert=False)
                except Exception:
                    pass
            audit(uid, "flood_blocked", count=len(bucket))
            return

        bucket.append(now)
        return await handler(event, data)
