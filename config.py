"""
Общая конфигурация проекта.
Читает переменные окружения из .env и предоставляет их всем модулям.
"""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    # Токен Telegram-бота
    BOT_TOKEN: str
    # ID администратора Telegram
    ADMIN_ID: int
    # URL мини-приложения (должен быть HTTPS для WebApp)
    WEBAPP_URL: str = "https://example.com"
    # Подключение к БД
    DATABASE_URL: str = "sqlite+aiosqlite:///./db/blacklotus.db"
    # Порт FastAPI
    WEBAPP_PORT: int = 8080

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def async_database_url(self) -> str:
        """
        Возвращает URL с драйвером aiosqlite (если задан обычный sqlite:///).
        SQLAlchemy async требует явного указания асинхронного драйвера.
        """
        url = self.DATABASE_URL
        if url.startswith("sqlite:///") and "+aiosqlite" not in url:
            url = url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
        return url


# Единый экземпляр настроек на весь проект
settings = Settings()
