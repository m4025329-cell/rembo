"""
Безопасное хеширование паролей и токенов пользователей.

bcrypt: адаптивный, устойчивый к rainbow-таблицам, cost=12 по умолчанию.
Используй для любых паролей/API-токенов, которые нужно проверять, но
никогда не показывать в открытом виде.
"""
import bcrypt


def hash_password(password: str, rounds: int = 12) -> str:
    """Захешировать пароль. Соль генерируется автоматически."""
    if not password:
        raise ValueError("Пустой пароль")
    salted = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=rounds))
    return salted.decode()


def verify_password(password: str, hashed: str) -> bool:
    """Проверить пароль по сохранённому хешу."""
    if not password or not hashed:
        return False
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except (ValueError, TypeError):
        return False
