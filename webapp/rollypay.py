"""
Интеграция с RollyPay — создание платежей и верификация вебхуков.

Документация: https://docs.rollypay.io
SDK: pip install rollypay (не используем, чтобы не тянуть лишнюю зависимость)

Поток:
1. POST /api/v1/payments → получаем payment_id + pay_url
2. Клиент переходит на pay_url
3. RollyPay шлёт webhook (payment.paid / payment.canceled) на callback_url
4. Мы верифицируем HMAC-SHA256 подпись и обновляем статус
"""
import hashlib
import hmac
import logging
import time
from uuid import uuid4

import aiohttp

from config import settings

logger = logging.getLogger("blacklotus.rollypay")

# Максимальный возраст вебхука (5 минут) — защита от replay-атак
WEBHOOK_MAX_AGE_SECONDS = 300


async def create_payment(
    amount: float,
    order_id: str,
    plan: str,
    customer_id: str,
    description: str | None = None,
    redirect_url: str | None = None,
) -> dict:
    """
    Создать платёж в RollyPay.

    Возвращает dict с полями:
      - payment_id: str — ID платежа в RollyPay
      - pay_url: str — URL для перенаправления клиента на оплату
      - status: str — начальный статус (обычно "pending")

    Raises:
        ValueError: если RollyPay не настроен
        aiohttp.ClientError: при сетевых ошибках
        RuntimeError: при ошибке API (не 2xx)
    """
    if not settings.ROLLYPAY_API_KEY:
        raise ValueError("ROLLYPAY_API_KEY не задан — оплата невозможна")

    payload = {
        "amount": amount,
        "order_id": order_id,
        "description": description or f"BlackLotusVPN — {plan}",
        "customer_id": customer_id,
    }
    if redirect_url:
        payload["redirect_url"] = redirect_url

    url = f"{settings.ROLLYPAY_API_URL.rstrip('/')}/api/v1/payments"
    headers = {
        "Authorization": f"Bearer {settings.ROLLYPAY_API_KEY}",
        "Content-Type": "application/json",
    }

    async with aiohttp.ClientSession() as http:
        async with http.post(
            url, json=payload, headers=headers,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            body = await resp.json()
            if resp.status >= 400:
                logger.error(
                    "RollyPay create_payment error %s: %s", resp.status, body
                )
                raise RuntimeError(
                    f"RollyPay API error {resp.status}: "
                    f"{body.get('message', body)}"
                )
            logger.info(
                "RollyPay payment created: order=%s, id=%s",
                order_id, body.get("payment_id"),
            )
            return body


def verify_webhook_signature(
    body: bytes,
    signature: str,
    timestamp: str,
) -> bool:
    """
    Проверить подпись RollyPay webhook.

    Формат подписи: HMAC-SHA256("timestamp.body", signing_secret)
    Заголовки: X-Signature, X-Timestamp
    """
    if not settings.ROLLYPAY_SIGNING_SECRET:
        logger.error("ROLLYPAY_SIGNING_SECRET не задан — вебхуки отклоняются")
        return False

    # Защита от replay: проверяем, что timestamp не слишком старый
    try:
        ts = int(timestamp)
    except (ValueError, TypeError):
        logger.warning("Invalid webhook timestamp: %s", timestamp)
        return False

    age = abs(time.time() - ts)
    if age > WEBHOOK_MAX_AGE_SECONDS:
        logger.warning(
            "Webhook timestamp too old: %d seconds (max %d)",
            age, WEBHOOK_MAX_AGE_SECONDS,
        )
        return False

    # HMAC-SHA256 от "timestamp.body"
    message = f"{timestamp}.".encode() + body
    expected = hmac.new(
        settings.ROLLYPAY_SIGNING_SECRET.encode(),
        message,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


def generate_order_id() -> str:
    """Уникальный order_id для платежа."""
    return f"bl-{uuid4().hex[:16]}"
