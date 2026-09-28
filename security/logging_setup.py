"""
Настройка логирования без утечки секретов + аудит-лог.

- SecretsFilter: вычищает BOT_TOKEN, FERNET_KEY, JWT_SECRET, vless://…
  и bearer-токены из любых лог-записей.
- audit_logger: пишет действия админа в logs/audit.log (не ротируем сами —
  оставляем logrotate/journald).
"""
import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config import settings, BASE_DIR


LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)


# Регексы, по которым будем маскировать чувствительные значения
_SECRETS_PATTERNS = [
    re.compile(re.escape(settings.BOT_TOKEN)) if settings.BOT_TOKEN else None,
    re.compile(re.escape(settings.FERNET_KEY)) if settings.FERNET_KEY else None,
    re.compile(re.escape(settings.JWT_SECRET)) if settings.JWT_SECRET else None,
    re.compile(r"vless://[^\s'\"]+"),
    re.compile(r"vmess://[^\s'\"]+"),
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]+", re.IGNORECASE),
    re.compile(r"\b[0-9]{9,10}:[A-Za-z0-9_\-]{35}\b"),   # TG bot-tokens вида id:hash
]
_SECRETS_PATTERNS = [p for p in _SECRETS_PATTERNS if p is not None]


class SecretsFilter(logging.Filter):
    """Заменяет секреты в тексте лог-записи на ***REDACTED***."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:
            return True
        redacted = msg
        for pat in _SECRETS_PATTERNS:
            redacted = pat.sub("***REDACTED***", redacted)
        if redacted != msg:
            # Перезаписываем сообщение и убираем args (они уже отрендерены)
            record.msg = redacted
            record.args = ()
        return True


def setup_logging(level: int = logging.INFO) -> None:
    """Установить глобальный логгер с фильтром секретов."""
    root = logging.getLogger()
    root.setLevel(level)
    # Убираем дубликаты хендлеров при повторной инициализации
    for h in list(root.handlers):
        root.removeHandler(h)

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )
    stream = logging.StreamHandler()
    stream.setFormatter(fmt)
    stream.addFilter(SecretsFilter())
    root.addHandler(stream)

    # Файловый лог общего назначения (5MB × 3 файла)
    file_h = RotatingFileHandler(
        LOGS_DIR / "app.log", maxBytes=5 * 1024 * 1024, backupCount=3,
        encoding="utf-8",
    )
    file_h.setFormatter(fmt)
    file_h.addFilter(SecretsFilter())
    root.addHandler(file_h)


# ── Аудит-лог ──────────────────────────────────────────────────────

audit_logger = logging.getLogger("blacklotus.audit")
_audit_configured = False


def _ensure_audit() -> None:
    global _audit_configured
    if _audit_configured:
        return
    audit_logger.setLevel(logging.INFO)
    audit_logger.propagate = False
    h = RotatingFileHandler(
        LOGS_DIR / "audit.log", maxBytes=5 * 1024 * 1024, backupCount=10,
        encoding="utf-8",
    )
    h.setFormatter(logging.Formatter(
        "%(asctime)s | AUDIT | %(message)s"
    ))
    h.addFilter(SecretsFilter())
    audit_logger.addHandler(h)
    _audit_configured = True


def audit(actor_id: int, action: str, **fields) -> None:
    """
    Записать действие в audit.log.
    Пример: audit(admin_id, 'grant_subscription', target=123, plan='3m')
    """
    _ensure_audit()
    extras = " ".join(f"{k}={v}" for k, v in fields.items())
    audit_logger.info(f"actor={actor_id} action={action} {extras}")
