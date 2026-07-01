from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[3]
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    app_name: str = "Mag2Read"
    app_env: str = "development"
    debug: bool = True
    api_prefix: str = "/api"

    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = ""
    mysql_database: str = "mag2read"

    redis_host: str = "127.0.0.1"
    redis_port: int = 6379
    redis_db: int = 0

    storage_root: str = str(PROJECT_ROOT / "backend" / "storage" / "tasks")
    paddlex_cache_root: str = str(PROJECT_ROOT / "backend" / "storage" / "paddlex_cache")
    max_upload_size_mb: int = 100
    baidu_ocr_api_key: str | None = None
    baidu_ocr_secret_key: str | None = None
    baidu_ocr_access_token: str | None = None
    auth_cookie_name: str = "mag2read_session"
    auth_session_days: int = 14
    auth_code_ttl_minutes: int = 5
    auth_code_send_interval_seconds: int = 60
    auth_code_secret: str = "change-me"
    smtp_host: str | None = None
    smtp_port: int = 465
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str | None = None
    wechat_app_id: str | None = None
    wechat_app_secret: str | None = None
    wechat_redirect_uri: str | None = None
    auth_captcha_enabled: bool = False
    turnstile_secret_key: str | None = None

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
            "?charset=utf8mb4"
        )

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # Aliyun (Alibaba Cloud) Machine Translation
    aliyun_translate_access_key: str | None = None
    aliyun_translate_secret_key: str | None = None
    aliyun_translate_region: str = "cn-hangzhou"

    # Baidu Translation (separate from Baidu OCR credentials)
    baidu_translate_app_id: str | None = None
    baidu_translate_secret_key: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
