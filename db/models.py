"""
ORM-модели SQLAlchemy для BlackLotusVPN.
Три сущности:
- User        — Telegram-пользователь
- Subscription — активная подписка (один-к-одному с User)
- VPNKey      — сгенерированные VPN-ключи
- SupportMessage — сообщения из формы поддержки
"""
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Boolean, ForeignKey, Text, Float
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Базовый класс для всех моделей."""
    pass


class User(Base):
    """Пользователь Telegram-бота."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Telegram user_id — уникальный идентификатор пользователя в TG
    tg_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # Дата первой регистрации в боте
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # Флаг активной подписки (упрощённо; детали в Subscription)
    is_subscribed: Mapped[bool] = mapped_column(Boolean, default=False)
    # Забанен ли пользователь администратором
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)

    subscription: Mapped["Subscription | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    keys: Mapped[list["VPNKey"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Subscription(Base):
    """Подписка пользователя на VPN."""
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    # План: 1m / 3m / 12m
    plan: Mapped[str] = mapped_column(String(16))
    # Дата активации подписки
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # Дата окончания
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    # Сколько заплатил (для статистики дохода)
    price: Mapped[float] = mapped_column(Float, default=0.0)

    user: Mapped[User] = relationship(back_populates="subscription")


class VPNKey(Base):
    """Сгенерированный VPN-ключ."""
    __tablename__ = "vpn_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    # Название страны/сервера
    country: Mapped[str] = mapped_column(String(64))
    # Сам ключ, зашифрован Fernet (base64-токен ~400 симв.)
    key_value: Mapped[str] = mapped_column(String(1024))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped[User] = relationship(back_populates="keys")


class DeviceSlot(Base):
    """
    Слот доп. устройства пользователя.
    Первое устройство входит в тариф бесплатно (в этой таблице не хранится),
    все последующие — платные (см. DEVICE_PRICE в .env).
    """
    __tablename__ = "device_slots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Ссылка на подписку/доступ (access) — здесь на пользователя
    access_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    # Пользовательское имя устройства (iPhone, Windows-ноут и т.п.)
    device_name: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship()


class Payment(Base):
    """
    Запись о платеже через RollyPay.
    Хранит состояние от создания до получения вебхука.
    """
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    order_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    rollypay_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    plan: Mapped[str] = mapped_column(String(16))
    amount: Mapped[float] = mapped_column(Float)
    payment_method: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    pay_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped[User] = relationship()


class SupportMessage(Base):
    """Сообщение из формы поддержки в мини-приложении."""
    __tablename__ = "support_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
