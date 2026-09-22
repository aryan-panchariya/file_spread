"""Configuration loaded from the local .env file."""

from __future__ import annotations

from functools import lru_cache

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings. Values come from environment variables or .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    bot_token: SecretStr
    admin_ids: str = ""
    database_url: str = "sqlite+aiosqlite:///data/bot.db"
    auto_delete_minutes: int = 20
    force_subscription_enabled: bool = False
    required_channel_id: str | None = None
    required_channel_username: str | None = None
    vplink_api_token: SecretStr | None = None
    vplink_enabled: bool = False

    @field_validator("auto_delete_minutes")
    @classmethod
    def auto_delete_minutes_must_be_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("AUTO_DELETE_MINUTES must be greater than zero.")
        return value

    @model_validator(mode="after")
    def validate_vplink_configuration(self) -> "Settings":
        if self.vplink_enabled and not self.vplink_api_token:
            raise ValueError("VPLINK_ENABLED=true requires VPLINK_API_TOKEN.")
        return self

    @property
    def parsed_admin_ids(self) -> set[int]:
        """Return ADMIN_IDS as numeric Telegram IDs; used beginning in Phase 2."""
        if not self.admin_ids.strip():
            return set()
        try:
            return {int(item.strip()) for item in self.admin_ids.split(",") if item.strip()}
        except ValueError as error:
            raise ValueError("ADMIN_IDS must be comma-separated numeric Telegram IDs.") from error


@lru_cache
def get_settings() -> Settings:
    """Build settings once, so startup fails clearly for invalid configuration."""
    return Settings()
