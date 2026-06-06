from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    api_base_url: str = "http://api:8000"
    fake_portal_base_url: str = "http://fake-portal:3000"
    fake_portal_username: str = "demo"
    fake_portal_password: str = "demo123"

    worker_poll_interval_seconds: int = 10
    worker_headless: bool = True
    worker_screenshot_dir: str = "/app/artifacts/screenshots"
    worker_html_snapshot_dir: str = "/app/artifacts/html_snapshots"


settings = Settings()
