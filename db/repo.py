"""
Слой доступа к данным (репозиторий).
Здесь собраны функции, которыми пользуется и бот, и веб-приложение.
"""
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import User, Subscription, VPNKey, SupportMessage, DeviceSlot
from security.crypto import encrypt, try_decrypt


# Цена базовой подписки (руб/мес) и цена доп. устройства (руб/мес)
# — читаются из .env для быстрой смены без деплоя.
import os
BASE_PRICE = float(os.getenv("BASE_PRICE", "150"))
DEVICE_PRICE = float(os.getenv("DEVICE_PRICE", "75"))


# Тарифы: длительность (дни) и цена (рубли) — 1 устройство включено в цену
PLANS = {
    "1m": {"days": 30, "price": 150.0, "title": "1 устройство / 30 дней"},
    "3m": {"days": 90, "price": 350.0, "title": "1 устройство / 90 дней"},
    "6m": {"days": 180, "price": 600.0, "title": "1 устройство / 180 дней"},
}

# Список серверов (hardcode-заглушка)
SERVERS = [
    {"code": "nl", "name": "Нидерланды", "flag": "🇳🇱"},
    {"code": "de", "name": "Германия", "flag": "🇩🇪"},
    {"code": "us", "name": "США", "flag": "🇺🇸"},
    {"code": "fi", "name": "Финляндия", "flag": "🇫🇮"},
    {"code": "jp", "name": "Япония", "flag": "🇯🇵"},
]


# ------------------------- Пользователи -------------------------

async def get_or_create_user(
    session: AsyncSession,
    tg_id: int,
    username: str | None = None,
    full_name: str | None = None,
) -> User:
    """Вернуть пользователя по tg_id, создав если ещё нет."""
    result = await session.execute(
        select(User)
        .where(User.tg_id == tg_id)
        .options(selectinload(User.subscription))
    )
    user = result.scalar_one_or_none()
    if user is None:
        user = User(tg_id=tg_id, username=username, full_name=full_name)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        # refresh() подгружает только колонки, не relationships — без этого
        # первое же обращение к user.subscription лениво лезет в БД вне
        # greenlet-контекста и падает 500 (SQLAlchemy async lazy-load).
        # У только что созданного юзера подписки гарантированно нет.
        user.subscription = None
        user._is_new = True  # ponytail: transient flag, not persisted
    else:
        # Sync profile — Telegram names change
        changed = False
        if username and user.username != username:
            user.username = username
            changed = True
        if full_name and user.full_name != full_name:
            user.full_name = full_name
            changed = True
        if changed:
            await session.commit()
        user._is_new = False
    return user


async def get_user_by_tg_id(session: AsyncSession, tg_id: int) -> User | None:
    """Найти пользователя по Telegram id (без создания)."""
    result = await session.execute(
        select(User)
        .where(User.tg_id == tg_id)
        .options(selectinload(User.subscription), selectinload(User.keys))
    )
    return result.scalar_one_or_none()


async def get_all_user_ids(session: AsyncSession) -> list[int]:
    """Все Telegram-ID для рассылки."""
    result = await session.execute(select(User.tg_id).where(User.is_banned == False))  # noqa: E712
    return [row[0] for row in result.all()]


# ------------------------- Подписки -------------------------

async def grant_subscription(
    session: AsyncSession,
    user: User,
    plan: str,
    price: float | None = None,
) -> Subscription:
    """Активировать подписку пользователю на указанный план."""
    if plan not in PLANS:
        raise ValueError(f"Неизвестный тариф: {plan}")
    days = PLANS[plan]["days"]
    price = PLANS[plan]["price"] if price is None else price

    now = datetime.utcnow()
    expires = now + timedelta(days=days)

    if user.subscription:
        # Продлеваем существующую подписку
        user.subscription.plan = plan
        user.subscription.started_at = now
        user.subscription.expires_at = expires
        user.subscription.price = price
    else:
        sub = Subscription(
            user_id=user.id,
            plan=plan,
            started_at=now,
            expires_at=expires,
            price=price,
        )
        session.add(sub)
        user.subscription = sub

    user.is_subscribed = True
    await session.commit()
    await session.refresh(user)
    return user.subscription


async def revoke_subscription(session: AsyncSession, user: User) -> None:
    """Отозвать подписку у пользователя."""
    if user.subscription:
        await session.delete(user.subscription)
    user.is_subscribed = False
    await session.commit()


# ------------------------- VPN-ключи -------------------------

async def generate_key(
    session: AsyncSession,
    user: User,
    country: str,
) -> VPNKey:
    """
    Заглушка генерации VPN-ключа.
    Возвращает случайный UUID; в реальности здесь будет запрос к панели VPN.

    Значение ключа шифруется Fernet перед сохранением в БД.
    """
    plaintext = f"vless://{uuid4()}@blacklotus.vpn:443?type=tcp#{country}"
    key = VPNKey(
        user_id=user.id,
        country=country,
        key_value=encrypt(plaintext),
    )
    session.add(key)
    await session.commit()
    await session.refresh(key)
    return key


async def list_keys(session: AsyncSession, user: User) -> list[VPNKey]:
    """Все ключи пользователя, свежие вверху. Значения дешифруются на лету."""
    result = await session.execute(
        select(VPNKey).where(VPNKey.user_id == user.id).order_by(VPNKey.created_at.desc())
    )
    keys = list(result.scalars().all())
    # try_decrypt устойчив к legacy-строкам (не зашифрованным)
    for k in keys:
        k.key_value = try_decrypt(k.key_value)
    return keys


# ------------------------- Доп. устройства -------------------------

async def count_devices(session: AsyncSession, user: User) -> int:
    """Сколько ДОПОЛНИТЕЛЬНЫХ устройств заведено (без 1-го бесплатного)."""
    result = await session.execute(
        select(func.count(DeviceSlot.id)).where(DeviceSlot.access_id == user.id)
    )
    return int(result.scalar_one() or 0)


async def add_device(
    session: AsyncSession, user: User, device_name: str
) -> DeviceSlot:
    """Добавить слот доп. устройства (в MVP без реальной оплаты)."""
    slot = DeviceSlot(access_id=user.id, device_name=device_name.strip()[:128])
    session.add(slot)
    await session.commit()
    await session.refresh(slot)
    return slot


async def list_devices(session: AsyncSession, user: User) -> list[DeviceSlot]:
    """Все доп. устройства пользователя, свежие вверху."""
    result = await session.execute(
        select(DeviceSlot)
        .where(DeviceSlot.access_id == user.id)
        .order_by(DeviceSlot.created_at.desc())
    )
    return list(result.scalars().all())


async def remove_device(session: AsyncSession, user: User, slot_id: int) -> bool:
    """Удалить слот доп. устройства. True, если что-то удалено."""
    result = await session.execute(
        select(DeviceSlot).where(
            DeviceSlot.id == slot_id, DeviceSlot.access_id == user.id
        )
    )
    slot = result.scalar_one_or_none()
    if slot is None:
        return False
    await session.delete(slot)
    await session.commit()
    return True


# ------------------------- Поддержка -------------------------

async def add_support_message(
    session: AsyncSession, user: User, text: str
) -> SupportMessage:
    """Сохранить обращение в поддержку."""
    msg = SupportMessage(user_id=user.id, text=text)
    session.add(msg)
    await session.commit()
    await session.refresh(msg)
    return msg


# ------------------------- Статистика -------------------------

async def stats(session: AsyncSession) -> dict:
    """Основные цифры для /admin."""
    total_users = (await session.execute(select(func.count(User.id)))).scalar_one()
    active_subs = (
        await session.execute(
            select(func.count(Subscription.id)).where(
                Subscription.expires_at > datetime.utcnow()
            )
        )
    ).scalar_one()
    revenue = (
        await session.execute(select(func.coalesce(func.sum(Subscription.price), 0)))
    ).scalar_one()
    return {
        "users": total_users,
        "active_subs": active_subs,
        "revenue": float(revenue or 0.0),
    }
