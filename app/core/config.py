from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(
        default="BestChoice PC Backend",
        validation_alias=AliasChoices("APP_NAME"),
    )
    log_level: str = Field(
        default="INFO",
        validation_alias=AliasChoices("LOG_LEVEL"),
    )
    mongo_uri: str = Field(
        default="mongodb://127.0.0.1:27017",
        validation_alias=AliasChoices("DB_URI", "MONGO_URI"),
    )
    mongo_database: str = Field(
        default="bestchoice_pc",
        validation_alias=AliasChoices("MONGODB_DATABASE", "MONGO_DATABASE"),
    )
    business_timezone: str = Field(
        default="America/Manaus",
        validation_alias=AliasChoices("BUSINESS_TIMEZONE"),
    )
    telegram_api_id: int | None = Field(
        default=None,
        validation_alias=AliasChoices("TELEGRAM_API_ID"),
    )
    telegram_api_hash: str | None = Field(
        default=None,
        validation_alias=AliasChoices("TELEGRAM_API_HASH"),
    )
    telegram_default_channel: str | None = Field(
        default="@pcbuildwizard",
        validation_alias=AliasChoices("TELEGRAM_DEFAULT_CHANNEL"),
    )
    telegram_session_path: str = Field(
        default=".telegram/session",
        validation_alias=AliasChoices("TELEGRAM_SESSION_PATH"),
    )
    openrouter_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("OPENROUTER_API_KEY"),
    )
    openrouter_model: str | None = Field(
        default=None,
        validation_alias=AliasChoices("OPENROUTER_MODEL"),
    )
    openrouter_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("OPENROUTER_ENABLED"),
    )
    redis_host: str = Field(
        default="redis",
        validation_alias=AliasChoices("REDIS_HOST"),
    )
    redis_port: int = Field(
        default=6379,
        validation_alias=AliasChoices("REDIS_PORT"),
    )
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
