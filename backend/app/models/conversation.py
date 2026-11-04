import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Conversation(Base):
    """Личный диалог двух участников (dm). Сообщения — обычные messages
    с заполненным conversation_id; в общей ленте conversation_id IS NULL."""

    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    members: Mapped[list["ConversationMember"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class ConversationMember(Base):
    """Участник диалога; last_read_message_id — для счётчика непрочитанных."""

    __tablename__ = "conversation_members"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    participant_token: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("participants.token", ondelete="CASCADE"), index=True
    )
    last_read_message_id: Mapped[int] = mapped_column(BigInteger, default=0)

    conversation: Mapped["Conversation"] = relationship(back_populates="members")
    participant: Mapped["Participant"] = relationship()
