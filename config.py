"""
Общая конфигурация проекта.

Все секреты читаются исключительно из .env через pydantic-settings.
Жёсткая валидация: если критичной переменной нет — процесс упадёт со
внятной ошибкой при старте, а не позже во время работы.
"""
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    """Настройки проекта. Ни один секрет не должен появиться в коде."""

    # ── Telegram ────────────────────────────────────────────────────
    BOT_TOKEN: str = Field(..., min_length=20, description="Токен @BotFather")
    ADMIN_ID: int = Field(..., description="Telegram user_id админа")

    # ── Мини-приложение ─────────────────────────────────────────────
    WEBAPP_URL: str = Field(..., min_length=1)
    WEBAPP_PORT: int = 8080
    ALLOWED_ORIGIN: str | None = None
    # В проде обязано быть False. Даёт fallback без initData — только для dev.
    DEBUG: bool = False

    # ── БД ──────────────────────────────────────────────────────────
    DATABASE_URL: str = "sqlite:///./db-data/blacklotus.db"
    DB_PASSWORD: str = ""

    # ── Шифрование секретов в БД ────────────────────────────────────
    FERNET_KEY: str = Field(..., min_length=44, description="Fernet base64-ключ")

    # ── Прочие секреты ─────────────────────────────────────────────
    JWT_SECRET: str = Field(..., min_length=16)
    XRAY_API_KEY: str = ""
    PAYMENT_SECRET: str = ""

    # ── Бэкапы ─────────────────────────────────────────────────────
    BACKUP_GPG_RECIPIENT: str = ""
    BACKUP_REMOTE: str = ""

    # ── Rate limit ──────────────────────────────────────────────────
    RATE_LIMIT_PER_MINUTE: int = 30
    BOT_FLOOD_LIMIT_PER_SECOND: int = 5

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Валидаторы ─────────────────────────────────────────────────

    @field_validator("BOT_TOKEN")
    @classmethod
    def _token_shape(cls, v: str) -> str:
        # Формат TG-токена: <int>:<строка>
        if ":" not in v or not v.split(":", 1)[0].isdigit():
            raise ValueError("BOT_TOKEN имеет неверный формат (нужно <id>:<hash>)")
        return v

    @field_validator("FERNET_KEY")
    @classmethod
    def _fernet_shape(cls, v: str) -> str:
        # Fernet-ключ — 32 байта, закодированные base64 → строка 44 символа
        from cryptography.fernet import Fernet, InvalidToken  # локальный импорт
        try:
            Fernet(v.encode())
        except (ValueError, InvalidToken) as e:
            raise ValueError(f"FERNET_KEY невалиден: {e}. Сгенерируй: "
                             "python -c 'from cryptography.fernet import Fernet; "
                             "print(Fernet.generate_key().decode())'")
        return v

    @field_validator("WEBAPP_URL")
    @classmethod
    def _webapp_url_https(cls, v: str) -> str:
        # В боевом режиме WEBAPP_URL обязан быть https
        if not (v.startswith("https://") or v.startswith("http://localhost")
                or v.startswith("http://127.0.0.1")):
            raise ValueError("WEBAPP_URL должен начинаться с https:// "
                             "(или http://localhost для dev)")
        return v

    # ── Утилиты ─────────────────────────────────────────────────────

    @property
    def async_database_url(self) -> str:
        """SQLAlchemy async требует явного драйвера aiosqlite."""
        url = self.DATABASE_URL
        if url.startswith("sqlite:///") and "+aiosqlite" not in url:
            url = url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
        return url

    @property
    def sqlite_path(self) -> Path | None:
        """Локальный путь к SQLite-файлу (для chmod 600)."""
        url = self.DATABASE_URL
        if url.startswith("sqlite:///"):
            return (BASE_DIR / url.removeprefix("sqlite:///")).resolve()
        return None

    @property
    def is_prod(self) -> bool:
        return not self.DEBUG

    def masked(self) -> dict[str, Any]:
        """Настройки для лога (все секреты замаскированы)."""
        d = self.model_dump()
        for key in (
            "BOT_TOKEN", "FERNET_KEY", "JWT_SECRET", "XRAY_API_KEY",
            "PAYMENT_SECRET", "DB_PASSWORD",
        ):
            if d.get(key):
                d[key] = "***"
        return d


try:
    settings = Settings()  # type: ignore[call-arg]
except ValidationError as exc:
    # Понятный вывод и завершение — не даём боту стартовать без секретов
    import sys
    print("\n❌ Ошибка конфигурации BlackLotusVPN:", file=sys.stderr)
    for err in exc.errors():
        loc = ".".join(str(x) for x in err["loc"])
        print(f"  · {loc}: {err['msg']}", file=sys.stderr)
    print("\nЗаполни .env по образцу .env.example и запусти снова.\n",
          file=sys.stderr)
    sys.exit(1)
