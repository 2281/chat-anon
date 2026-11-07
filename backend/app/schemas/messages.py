from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

ReactionKind = Literal["like", "dislike"]


class ReactionSet(BaseModel):
    kind: ReactionKind


class MessageCreate(BaseModel):
    text: str = Field(default="", max_length=4000)
    reply_to_id: int | None = None
    quote_message_id: int | None = None
    quote_excerpt: str | None = Field(default=None, max_length=1000)
    attachment_ids: list[int] = Field(default_factory=list, max_length=10)


class MessageUpdate(BaseModel):
    """Полное желаемое состояние сообщения: текст и набор вложений целиком."""

    text: str = Field(default="", max_length=4000)
    attachment_ids: list[int] = Field(default_factory=list, max_length=10)


class AttachmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    file_name: str
    mime_type: str
    size: int


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    text: str
    author_token: UUID
    author_nickname: str
    reply_to_id: int | None
    quote_message_id: int | None
    quote_excerpt: str | None
    created_at: datetime
    edited_at: datetime | None = None
    attachments: list[AttachmentOut]
    likes: int
    dislikes: int
    my_reaction: ReactionKind | None = None
    # все потомки (ответы, ответы на ответы...) плоским списком по id ASC;
    # заполняется только в GET /api/messages для корневых сообщений
    replies: list["MessageOut"] = []


MessageOut.model_rebuild()


class MessagePage(BaseModel):
    items: list[MessageOut]
    # id самого старого сообщения страницы — курсор для подгрузки более ранней истории;
    # None — история закончилась
    next_cursor: int | None


class SearchHit(BaseModel):
    """Найденное сообщение: conversation_id None — общий чат, иначе id личного диалога."""

    conversation_id: int | None
    message: MessageOut


class SearchResults(BaseModel):
    items: list[SearchHit]
