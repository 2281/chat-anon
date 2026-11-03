from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent  # корень репозитория


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+asyncpg://chat:chat@localhost:5433/chatanon"

    s3_endpoint_url: str = "http://localhost:9000"
    # endpoint для серверных вызовов (внутри docker-сети); для хоста совпадает с s3_endpoint_url
    s3_internal_endpoint_url: str = "http://localhost:9000"
    # если задан, host в presigned URL заменяется на этот адрес (dev: Vite проксирует
    # пути бакета на MinIO, браузер работает только с одним origin — без CORS)
    s3_proxy_base_url: str = ""
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "chatanon"
    s3_region: str = "us-east-1"


settings = Settings()
