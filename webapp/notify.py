"""
Доставка кода подтверждения регистрации: почта (SMTP) или SMS (sms.ru).

Без настроенных SMTP_*/SMS_RU_API_ID код просто пишется в лог — удобно
для разработки, ничего не ломает. В проде обязательно заполнить ключи
(см. .env.example), иначе пользователь не получит код и не сможет
подтвердить регистрацию.
"""
import logging
import smtplib
from email.mime.text import MIMEText

import aiohttp

from config import settings

logger = logging.getLogger("blacklotus.notify")


async def send_verification_code(channel: str, target: str, code: str) -> None:
    """Отправить код по email или телефону. channel: 'email' | 'phone'."""
    if channel == "email":
        await _send_email(target, code)
    else:
        await _send_sms(target, code)


async def _send_email(to: str, code: str) -> None:
    if not settings.has_smtp:
        logger.warning("SMTP не настроен — код для %s: %s (dev)", to, code)
        return
    msg = MIMEText(
        f"Код подтверждения {settings.SERVICE_NAME}: {code}\n"
        f"Действует 10 минут. Если это были не вы — проигнорируйте письмо."
    )
    msg["Subject"] = f"{settings.SERVICE_NAME}: код подтверждения"
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to

    import asyncio
    await asyncio.to_thread(_smtp_send, to, msg)


def _smtp_send(to: str, msg: MIMEText) -> None:
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
        server.starttls()
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_FROM, [to], msg.as_string())


async def _send_sms(to: str, code: str) -> None:
    if not settings.has_sms:
        logger.warning("SMS не настроен — код для %s: %s (dev)", to, code)
        return
    text = f"{settings.SERVICE_NAME}: код {code}"
    async with aiohttp.ClientSession() as http:
        async with http.get(
            "https://sms.ru/sms/send",
            params={"api_id": settings.SMS_RU_API_ID, "to": to, "msg": text, "json": 1},
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            data = await resp.json()
            if data.get("status") != "OK":
                logger.error("sms.ru: не удалось отправить код на %s: %s", to, data)
