"""Глобальные настройки JARVIS через pydantic-settings (читает .env)."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class JarvisSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Telegram — боты
    telegram_bot_token: str = Field(default="")
    owner_user_id: int = Field(default=374728252)
    rafail_bot_token: str = Field(default="")
    jarvis_notify_bot_token: str = Field(default="")
    jarvis_work_bot_token: str = Field(default="")

    # Telegram — чаты и топики
    rafail_chat_id: int = Field(default=-1003891647143)
    rafail_topic_id: int = Field(default=205)
    work_chat_id: int = Field(default=-1003891647143)
    work_topic_id: int = Field(default=202)
    inbox_chat_id: int = Field(default=-1003891647143)
    inbox_topic_id: int = Field(default=2)

    # Kommo CRM
    kommo_token: str = Field(default="")
    kommo_domain: str = Field(default="lkenergy.kommo.com")

    # Ringostat
    ringostat_webhook_secret: str = Field(default="")
    ringostat_auth_key: str = Field(default="")
    ringostat_project_id: int = Field(default=167416)

    # Gemini / LLM — GEMINI_KEYS хранится в .env через запятую, не JSON
    gemini_keys: str = Field(default="")
    gemini_model: str = Field(default="gemini-2.5-flash")
    rafail_model: str = Field(default="gemini-2.5-flash")
    rafail_model_quality: str = Field(default="gemini-2.5-flash")

    # Moodle
    moodle_url: str = Field(default="https://my.lk-energy.com.ua")
    moodle_token: str = Field(default="")

    def get_gemini_keys(self) -> list[str]:
        return [k.strip() for k in self.gemini_keys.split(",") if k.strip()]


_settings: JarvisSettings | None = None


def get_settings() -> JarvisSettings:
    global _settings
    if _settings is None:
        _settings = JarvisSettings()
    return _settings
