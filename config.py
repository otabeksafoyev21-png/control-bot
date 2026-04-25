"""Application configuration loaded from environment / .env."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Telegram userbot (MTProto) — https://my.telegram.org/apps
    TELEGRAM_API_ID: int
    TELEGRAM_API_HASH: str
    TELEGRAM_STRING_SESSION: str = ""

    # Control bot (Bot API) — @BotFather
    CONTROL_BOT_TOKEN: str
    OWNER_ID: int

    # Kaworai_bot SECRET_CHANNEL_ID — shu yerga video yuboriladi "ID: X\nQism: Y"
    # formatida. Kaworai_bot o'zining mavjud handleri bilan DB-ga yozadi.
    SECRET_CHANNEL_ID: int

    # Watcher o'z state'ini saqlaydigan SQLite fayli (kanal→anime map, dedup)
    SQLITE_PATH: str = "watcher.db"

    # Kaworai bot PostgreSQL — anime nomi va ID sini olish uchun.
    # Bo'sh bo'lsa — faqat mahalliy SQLite anime jadvali ishlatiladi.
    KAWORAI_DATABASE_URL: str = ""

    # Parser
    MIN_VIDEO_DURATION: int = 60

    # Avtojavob kechikishi (soniyalarda) — odamday gaplashish uchun
    AUTO_REPLY_MIN_DELAY: int = 60
    AUTO_REPLY_MAX_DELAY: int = 120

    LOG_LEVEL: str = Field(default="INFO")


settings = Settings()  # type: ignore[call-arg]
