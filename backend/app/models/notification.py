import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Notification(Base):
    """Уведомление участника: ответ в его ветке (kind="reply") или оценка его
    сообщения (kind="like"/"dislike").

    is_read=False — «непрочитанное» (пользователь по нему ещё не кликал).
    """

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    participant_token: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("participants.token", ondelete="CASCADE"), index=True
    )
    # сообщение, к которому ведёт уведомление (ответ / оценённое); каскад при его удалении
    message_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("messages.id", ondelete="CASCADE"), index=True
    )
    # reply | like | dislike
    kind: Mapped[str] = mapped_column(String(16), default="reply", server_default="reply")
    # кто спровоцировал уведомление (автор ответа / оценивший);
    # у записей до появления колонки NULL — подставляется автор сообщения
    actor_token: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("participants.token", ondelete="SET NULL")
    )
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    message: Mapped["Message"] = relationship()
    # два FK ведут на participants — связь с актором указываем явно
    actor: Mapped["Participant"] = relationship(foreign_keys=[actor_token])
