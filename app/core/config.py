from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(
        default="BestChoice PC Backend",
        validation_alias=AliasChoices("APP_NAME"),
    )
    mongo_uri: str = Field(
        default="mongodb://127.0.0.1:27017",
        validation_alias=AliasChoices("DB_URI", "MONGO_URI"),
    )
    mongo_database: str = Field(
        default="bestchoice_pc",
        validation_alias=AliasChoices("MONGODB_DATABASE", "MONGO_DATABASE"),
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
