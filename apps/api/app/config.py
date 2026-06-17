from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    discord_client_id: str = Field(validation_alias="DISCORD_CLIENT_ID")
    discord_client_secret: str = Field(validation_alias="DISCORD_CLIENT_SECRET")
    discord_bot_token: str = Field(validation_alias="DISCORD_BOT_TOKEN")
    discord_guild_id: str = Field(validation_alias="DISCORD_GUILD_ID")
    database_url: str = Field(validation_alias="DATABASE_URL")
    redis_url: str = Field(default="redis://localhost:6379/0", validation_alias="REDIS_URL")
    session_secret: str = Field(validation_alias="SESSION_SECRET")
    api_internal_secret: str = Field(validation_alias="API_INTERNAL_SECRET")
    nextauth_secret: str = Field(validation_alias="NEXTAUTH_SECRET")
    nextauth_url: str = Field(default="http://localhost:3000", validation_alias="NEXTAUTH_URL")
    api_url: str = Field(default="http://localhost:8000", validation_alias="API_URL")
    # Comma-separated list of allowed CORS origins (overrides nextauth_url for multi-origin setups)
    cors_origins: str = Field(default="", validation_alias="CORS_ORIGINS")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
