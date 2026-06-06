from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://rideportal:rideportal@postgres:5432/rideportal"

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""


settings = Settings()
