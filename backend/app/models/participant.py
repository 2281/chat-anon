import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Participant(Base):
    __tablename__ = "participants"

    token: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    # идентичность пользователя: вход по email выдаёт существующую запись;
    # nullable — у записей, созданных до появления email, его нет
    email: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    nickname: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    messages: Mapped[list["Message"]] = relationship(back_populates="participant")
