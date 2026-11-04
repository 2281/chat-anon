from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.messages import MessageOut


class ConversationCreate(BaseModel):
    # с кем открыть личный диалог
    participant_token: UUID


class ConversationOut(BaseModel):
    id: int
    peer_token: UUID
    peer_nickname: str
    last_message: MessageOut | None
    unread_count: int


class DmMessageCreate(BaseModel):
    text: str = Field(default="", max_length=4000)
    attachment_ids: list[int] = Field(default_factory=list, max_length=10)


class DmMessagePage(BaseModel):
    items: list[MessageOut]
    next_cursor: int | None


class ReadMark(BaseModel):
    last_read_message_id: int = Field(ge=0)
