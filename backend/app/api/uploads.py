import os.path
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_participant, get_db
from app.models import Attachment, Message, Participant
from app.services.conversations import get_member
from app.storage.s3 import presign_download, presign_upload

router = APIRouter(tags=["uploads"])

# лимит из README — 100 МБ на файл
MAX_FILE_SIZE = 100 * 1024 * 1024
ALLOWED_MIME_PREFIXES = ("image/", "audio/", "video/")
ALLOWED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp",
    ".mp3", ".ogg", ".wav", ".m4a", ".aac", ".flac",
    ".mp4", ".webm", ".mov", ".mkv", ".avi",
}


class PresignRequest(BaseModel):
    file_name: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(min_length=1, max_length=127)
    size: int = Field(ge=1, le=MAX_FILE_SIZE)


class PresignResponse(BaseModel):
    attachment_id: int
    upload_url: str


@router.post("/api/uploads/presign", response_model=PresignResponse)
async def create_presigned_upload(
    data: PresignRequest,
    db: AsyncSession = Depends(get_db),
    participant: Participant = Depends(get_current_participant),
) -> PresignResponse:
    if not data.mime_type.startswith(ALLOWED_MIME_PREFIXES):
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "разрешены только изображения, аудио и видео",
        )
    extension = os.path.splitext(data.file_name)[1].lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"расширение файла {extension!r} не разрешено",
        )

    # s3_key безопасен: uuid + расширение из белого списка
    key = f"attachments/{uuid.uuid4().hex}{extension}"
    attachment = Attachment(
        s3_key=key,
        file_name=data.file_name,
        mime_type=data.mime_type,
        size=data.size,
    )
    db.add(attachment)
    await db.commit()
    await db.refresh(attachment)
    return PresignResponse(
        attachment_id=attachment.id,
        upload_url=await presign_upload(key),
    )


@router.get("/api/attachments/{attachment_id}/file")
async def attachment_file(
    attachment_id: int,
    download: bool = Query(default=False),
    token: uuid.UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Отдача файла: редирект на presigned GET URL (short-lived).

    ?download=true — отдать с Content-Disposition: attachment (скачивание),
    без параметра — подходит для <img>/<audio>/<video> (inline-просмотр).
    Вложения личных диалогов требуют ?token= участника диалога (теги <img>
    не отправляют заголовки, поэтому токен — query-параметром).
    """
    attachment = await db.get(Attachment, attachment_id)
    if attachment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "вложение не найдено")
    if attachment.message_id is not None:
        message = await db.get(Message, attachment.message_id)
        if message is not None and message.conversation_id is not None:
            if token is None:
                raise HTTPException(
                    status.HTTP_401_UNAUTHORIZED, "вложение личного диалога требует token"
                )
            # 404 для чужих — не раскрываем существование диалога
            await get_member(db, message.conversation_id, token)
    url = await presign_download(attachment.s3_key, attachment.file_name, download)
    return RedirectResponse(url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
