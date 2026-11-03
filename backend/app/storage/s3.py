import inspect
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit

import aioboto3
from botocore.config import Config as BotoConfig

from app.config import settings

# presigned PUT — на загрузку файла; presigned GET — на отдачу в браузер
_PRESIGN_EXPIRES_UPLOAD = 15 * 60
_PRESIGN_EXPIRES_DOWNLOAD = 12 * 60 * 60


def _session() -> aioboto3.Session:
    return aioboto3.Session(
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
    )


def _client_args(endpoint_url: str) -> dict[str, Any]:
    return {
        "endpoint_url": endpoint_url,
        "config": BotoConfig(signature_version="s3v4"),
    }


async def ensure_bucket() -> None:
    """Создаёт бакет, если его нет (сервисные вызовы — по внутреннему endpoint)."""
    async with _session().client("s3", **_client_args(settings.s3_internal_endpoint_url)) as s3:
        buckets = await s3.list_buckets()
        names = [b["Name"] for b in buckets["Buckets"]]
        if settings.s3_bucket not in names:
            await s3.create_bucket(Bucket=settings.s3_bucket)


async def delete_object(key: str) -> None:
    """Удаляет объект из хранилища (сервисный вызов — по внутреннему endpoint)."""
    async with _session().client("s3", **_client_args(settings.s3_internal_endpoint_url)) as s3:
        await s3.delete_object(Bucket=settings.s3_bucket, Key=key)


async def presign_upload(key: str) -> str:
    """URL для прямой загрузки объекта из браузера (PUT).

    Подписывается на публичном endpoint — в URL должен быть адрес, доступный браузеру.
    """
    return await _presign("put_object", key, _PRESIGN_EXPIRES_UPLOAD)


async def presign_download(key: str, file_name: str, as_attachment: bool) -> str:
    """URL для скачивания/inline-отдачи объекта."""
    params: dict[str, Any] = {}
    if as_attachment:
        # filename* — RFC 5987, чтобы корректно отдавать не-ASCII имена
        safe_name = file_name.replace('"', "'")
        params["ResponseContentDisposition"] = (
            f"attachment; filename=\"{safe_name}\"; filename*=UTF-8''{quote(file_name)}"
        )
    return await _presign("get_object", key, _PRESIGN_EXPIRES_DOWNLOAD, params)


async def _presign(method: str, key: str, expires: int, params: dict[str, Any] | None = None) -> str:
    # при проксировании подписываем на внутреннем endpoint (именно его увидит MinIO
    # от прокси — changeOrigin в Vite/nginx подменяет Host), а в выдачу отдаём
    # ОТНОСИТЕЛЬНЫЙ URL (путь + query): браузер резолвит его от origin открытой
    # страницы, поэтому ссылки работают и с localhost, и с телефона по Wi-Fi
    sign_endpoint = (
        settings.s3_internal_endpoint_url if settings.s3_proxy_base_url else settings.s3_endpoint_url
    )
    async with _session().client("s3", **_client_args(sign_endpoint)) as s3:
        args: dict[str, Any] = {"Bucket": settings.s3_bucket, "Key": key}
        if params:
            args.update(params)
        url = s3.generate_presigned_url(method, Params=args, ExpiresIn=expires)
        if inspect.isawaitable(url):
            url = await url
    if settings.s3_proxy_base_url:
        parts = urlsplit(url)
        return urlunsplit(("", "", parts.path, parts.query, ""))
    return url
