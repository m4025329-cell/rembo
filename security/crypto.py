"""
Симметричное шифрование секретов, лежащих в БД (VPN-ключи, платёжные
данные и т.п.).

Ключ шифрования читается из .env → FERNET_KEY.
Никогда не хардкодь ключ.
"""
from cryptography.fernet import Fernet, InvalidToken

from config import settings


_fernet = Fernet(settings.FERNET_KEY.encode())


def encrypt(plaintext: str) -> str:
    """Зашифровать строку и вернуть base64-токен."""
    if plaintext is None:
        raise ValueError("Нельзя зашифровать None")
    return _fernet.encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str:
    """Расшифровать токен. Возвращает исходную строку или бросает исключение."""
    try:
        return _fernet.decrypt(token.encode()).decode()
    except InvalidToken as e:
        # Не логируем сам токен, чтобы не утек в лог
        raise ValueError("Не удалось расшифровать значение (неверный ключ)") from e


def try_decrypt(token: str) -> str:
    """
    Мягкий вариант: если строка не была зашифрована (legacy-данные),
    возвращает её как есть. Полезно при миграции.
    """
    try:
        return decrypt(token)
    except Exception:
        return token
