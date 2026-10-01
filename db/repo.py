"""
Слой доступа к данным (репозиторий).
Здесь собраны функции, которыми пользуется и бот, и веб-приложение.
"""
import random
import re
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import settings
from db.models import (
    User, Subscription, VPNKey, SupportMessage, DeviceSlot, VerificationCode,
)
from security.crypto import encrypt, try_decrypt
from security.passwords import hash_password, verify_password


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

class SubscriptionRequired(ValueError):
    """Нет активной подписки — ключ выдать нельзя."""


class DeviceLimitReached(ValueError):
    """Исчерпан лимит одновременных ключей (1 бесплатный + доп. устройства)."""


async def count_keys(session: AsyncSession, user: User) -> int:
    """Сколько ключей уже выдано пользователю."""
    result = await session.execute(
        select(func.count(VPNKey.id)).where(VPNKey.user_id == user.id)
    )
    return int(result.scalar_one() or 0)


async def generate_key(
    session: AsyncSession,
    user: User,
    country: str,
) -> VPNKey:
    """
    Выдать новый VPN-ключ.

    Требует активную подписку и свободный слот устройства (1 входит в тариф
    + сколько куплено в DeviceSlot). Если панель 3x-ui настроена (см.
    config.has_real_vpn_panel) — ключ реальный, клиент заводится в инбаунде.
    Иначе — DEMO-ключ (нерабочий, явно помечен), чтобы фронт/бот можно было
    разрабатывать и показывать без боевого сервера.

    Значение всегда шифруется Fernet перед сохранением в БД.
    """
    if not (user.subscription and user.is_subscribed):
        raise SubscriptionRequired("нужна активная подписка")

    limit = 1 + await count_devices(session, user)
    if await count_keys(session, user) >= limit:
        raise DeviceLimitReached(f"достигнут лимит устройств ({limit})")

    if settings.has_real_vpn_panel:
        from webapp.xui import create_client  # локальный импорт — без цикла webapp<->db
        plaintext = await create_client(f"tg{user.tg_id}-{country}")
    else:
        plaintext = f"vless://{uuid4()}@DEMO.blacklotus.vpn:443?type=tcp#DEMO-{country}"

    key = VPNKey(
        user_id=user.id,
        country=country,
        key_value=encrypt(plaintext),
    )
    session.add(key)
    await session.commit()
    await session.refresh(key)
    return key


async def revoke_key(session: AsyncSession, user: User, key_id: int) -> bool:
    """Удалить ключ: с панели (best-effort) и из БД. True, если что-то удалили."""
    result = await session.execute(
        select(VPNKey).where(VPNKey.id == key_id, VPNKey.user_id == user.id)
    )
    key = result.scalar_one_or_none()
    if key is None:
        return False
    if settings.has_real_vpn_panel:
        from webapp.xui import delete_client
        await delete_client(try_decrypt(key.key_value))
    await session.delete(key)
    await session.commit()
    return True


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


# ------------------------- Вход по email/телефону -------------------------
# Личный кабинет без Telegram: регистрация с паролем + код подтверждения.

CODE_TTL_MINUTES = 10
RESEND_COOLDOWN_SECONDS = 60
MAX_CODE_ATTEMPTS = 5

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_RE = re.compile(r"^\+?[1-9]\d{7,14}$")


class AuthError(ValueError):
    """Базовый класс ошибок входа/регистрации."""


class TargetTaken(AuthError):
    """Почта/телефон уже зарегистрированы."""


class InvalidTarget(AuthError):
    """Невалидный формат почты/телефона."""


class InvalidCredentials(AuthError):
    """Неверная почта/телефон или пароль."""


class NotVerified(AuthError):
    """Аккаунт создан, но код подтверждения ещё не введён."""


class InvalidCode(AuthError):
    """Неверный или просроченный код."""


class ResendCooldown(AuthError):
    """Код уже отправлялся недавно — подожди перед повторной отправкой."""


def normalize_target(channel: str, value: str) -> str:
    """Проверить формат и привести почту/телефон к каноническому виду."""
    value = (value or "").strip()
    if channel == "email":
        value = value.lower()
        if not _EMAIL_RE.match(value):
            raise InvalidTarget("некорректный email")
        return value
    # phone: оставляем только цифры и ведущий +
    digits = re.sub(r"[^\d+]", "", value)
    if not _PHONE_RE.match(digits):
        raise InvalidTarget("некорректный номер телефона")
    return digits if digits.startswith("+") else f"+{digits}"


async def get_user_by_id(session: AsyncSession, user_id: int) -> User | None:
    result = await session.execute(
        select(User).where(User.id == user_id).options(selectinload(User.subscription))
    )
    return result.scalar_one_or_none()


async def _get_user_by_target(session: AsyncSession, channel: str, target: str) -> User | None:
    col = User.email if channel == "email" else User.phone
    result = await session.execute(select(User).where(col == target))
    return result.scalar_one_or_none()


async def register_with_credentials(
    session: AsyncSession, channel: str, value: str, password: str
) -> tuple[User, str]:
    """
    Создать неподтверждённого пользователя и код подтверждения.
    Возвращает (user, code) — code отдаётся вызывающей стороне для отправки
    письма/SMS (сама функция ничего никуда не шлёт).
    """
    target = normalize_target(channel, value)
    if await _get_user_by_target(session, channel, target):
        raise TargetTaken(f"{channel} уже зарегистрирован")

    user = User(password_hash=hash_password(password))
    setattr(user, channel, target)
    session.add(user)
    await session.commit()
    await session.refresh(user)

    code = await _issue_code(session, channel, target)
    return user, code


async def resend_code(session: AsyncSession, channel: str, value: str) -> str:
    """Перегенерировать код (с троттлингом), вернуть его для отправки."""
    target = normalize_target(channel, value)
    user = await _get_user_by_target(session, channel, target)
    if user is None:
        raise InvalidTarget("аккаунт не найден")
    verified = user.email_verified if channel == "email" else user.phone_verified
    if verified:
        raise AuthError("уже подтверждено")
    return await _issue_code(session, channel, target)


async def _issue_code(session: AsyncSession, channel: str, target: str) -> str:
    result = await session.execute(
        select(VerificationCode)
        .where(VerificationCode.channel == channel, VerificationCode.target == target)
        .order_by(VerificationCode.created_at.desc())
    )
    last = result.scalars().first()
    if last and last.created_at > datetime.utcnow() - timedelta(seconds=RESEND_COOLDOWN_SECONDS):
        raise ResendCooldown("код уже отправлен, подожди перед повторной отправкой")

    code = f"{random.randint(0, 999999):06d}"
    row = VerificationCode(
        channel=channel,
        target=target,
        code_hash=hash_password(code),
        expires_at=datetime.utcnow() + timedelta(minutes=CODE_TTL_MINUTES),
    )
    session.add(row)
    await session.commit()
    return code


async def verify_registration_code(
    session: AsyncSession, channel: str, value: str, code: str
) -> User:
    """Проверить код, пометить канал подтверждённым. Возвращает User."""
    target = normalize_target(channel, value)
    result = await session.execute(
        select(VerificationCode)
        .where(VerificationCode.channel == channel, VerificationCode.target == target)
        .order_by(VerificationCode.created_at.desc())
    )
    row = result.scalars().first()
    if row is None or row.expires_at < datetime.utcnow():
        raise InvalidCode("код просрочен или не найден")
    if row.attempts >= MAX_CODE_ATTEMPTS:
        raise InvalidCode("слишком много попыток, запроси новый код")
    if not verify_password(code, row.code_hash):
        row.attempts += 1
        await session.commit()
        raise InvalidCode("неверный код")

    user = await _get_user_by_target(session, channel, target)
    if user is None:
        raise InvalidTarget("аккаунт не найден")
    setattr(user, f"{channel}_verified", True)
    await session.delete(row)
    await session.commit()
    await session.refresh(user)
    return user


async def login_with_credentials(
    session: AsyncSession, channel: str, value: str, password: str
) -> User:
    """Проверить пароль, убедиться что канал подтверждён. Возвращает User."""
    target = normalize_target(channel, value)
    user = await _get_user_by_target(session, channel, target)
    if user is None or not verify_password(password, user.password_hash or ""):
        raise InvalidCredentials("неверные данные для входа")
    verified = user.email_verified if channel == "email" else user.phone_verified
    if not verified:
        raise NotVerified("подтвердите аккаунт кодом из письма/SMS")
    if user.is_banned:
        raise InvalidCredentials("аккаунт заблокирован")
    return user


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
