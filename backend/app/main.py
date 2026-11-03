from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import messages, participants, uploads, ws
from app.storage.s3 import ensure_bucket


@asynccontextmanager
async def lifespan(app: FastAPI):
    # бакет создаёт compose-переменной MINIO_DEFAULT_BUCKETS, но проверка дешевле,
    # чем разбор ошибок presign при стёртом volume
    await ensure_bucket()
    yield


app = FastAPI(title="chat-anon", lifespan=lifespan)
app.include_router(participants.router)
app.include_router(messages.router)
app.include_router(uploads.router)
app.include_router(ws.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
