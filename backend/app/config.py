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
    # режим прокси: если задан (любое непустое значение), presigned URL выдаются
    # ОТНОСИТЕЛЬНЫМИ (путь бакета + подпись) — браузер ходит на origin открытой
    # страницы, а dev-сервер/proxy проксирует пути бакета на MinIO (без CORS);
    # относительные ссылки работают с любого устройства (localhost, телефон по Wi-Fi)
    s3_proxy_base_url: str = ""
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "chatanon"
    s3_region: str = "us-east-1"


settings = Settings()
