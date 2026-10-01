"""
Подписанные сессионные токены для входа по email/телефону (вне Telegram,
где нет initData). HMAC-SHA256 поверх JWT_SECRET — тот же принцип, что и
JWT, без лишней зависимости (pyjwt/itsdangerous не используются больше
нигде в проекте).
"""
import base64
import hashlib
import hmac
import json
import time

from config import settings

SESSION_TTL_DAYS = 30


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _sign(body: str) -> str:
    return _b64(hmac.new(settings.JWT_SECRET.encode(), body.encode(), hashlib.sha256).digest())


def create_session_token(user_id: int) -> str:
    """Выдать токен личного кабинета на SESSION_TTL_DAYS."""
    payload = {"uid": user_id, "exp": int(time.time()) + SESSION_TTL_DAYS * 86400}
    body = _b64(json.dumps(payload).encode())
    return f"{body}.{_sign(body)}"


def verify_session_token(token: str) -> int | None:
    """Вернуть user_id, если токен подлинный и не просрочен, иначе None."""
    if not token or "." not in token:
        return None
    body, sig = token.rsplit(".", 1)
    if not hmac.compare_digest(sig, _sign(body)):
        return None
    try:
        payload = json.loads(_unb64(body))
    except Exception:
        return None
    if payload.get("exp", 0) < time.time():
        return None
    uid = payload.get("uid")
    return int(uid) if isinstance(uid, (int, str)) and str(uid).isdigit() else None
