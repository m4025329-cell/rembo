"""
Проверка initData от Telegram WebApp.
Схема описана в https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""
import hashlib
import hmac
import json
from urllib.parse import parse_qsl

from config import settings


def verify_init_data(init_data: str) -> dict | None:
    """
    Проверить подпись initData и вернуть распарсенные поля.
    Возвращает None, если подпись неверна.
    """
    if not init_data:
        return None
    try:
        parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    except Exception:
        return None

    received_hash = parsed.pop("hash", None)
    if not received_hash:
        return None

    # data_check_string = key=value\n... в алфавитном порядке
    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(parsed.items())
    )
    secret_key = hmac.new(
        b"WebAppData", settings.BOT_TOKEN.encode(), hashlib.sha256
    ).digest()
    calc_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(calc_hash, received_hash):
        return None

    # Парсим поле user (JSON)
    user_field = parsed.get("user")
    if user_field:
        try:
            parsed["user"] = json.loads(user_field)
        except json.JSONDecodeError:
            return None
    return parsed
