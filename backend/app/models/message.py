import uuid
from datetime import datetime
from typing import ClassVar

from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, Text, func, select
from sqlalchemy.orm import Mapped, column_property, mapped_column, relationship

from app.db import Base
from app.models.reaction import Reaction


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    participant_token: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("participants.token", ondelete="CASCADE"), index=True
    )
    text: Mapped[str] = mapped_column(Text, default="")
    reply_to_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("messages.id", ondelete="SET NULL"), index=True
    )
    quote_message_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("messages.id", ondelete="SET NULL"), index=True
    )
    quote_excerpt: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    participant: Mapped["Participant"] = relationship(back_populates="messages")
    attachments: Mapped[list["Attachment"]] = relationship(
        back_populates="message", cascade="all, delete-orphan"
    )
    reactions: Mapped[list["Reaction"]] = relationship(
        back_populates="message", cascade="all, delete-orphan"
    )

    # счётчики реакций — вычисляемые подзапросы, не требуют миграции
    likes: Mapped[int] = column_property(
        select(func.count(Reaction.id))
        .where(Reaction.message_id == id, Reaction.kind == "like")
        .correlate_except(Reaction)
        .scalar_subquery()
    )
    dislikes: Mapped[int] = column_property(
        select(func.count(Reaction.id))
        .where(Reaction.message_id == id, Reaction.kind == "dislike")
        .correlate_except(Reaction)
        .scalar_subquery()
    )

    # реакция текущего участника: заполняется сервисом, в БД не хранится
    my_reaction: ClassVar[str | None] = None

    @property
    def author_nickname(self) -> str:
        # требует загруженного participant (см. _MESSAGE_LOAD в app/services/messages.py)
        return self.participant.nickname

    @property
    def author_token(self) -> uuid.UUID:
        return self.participant_token
