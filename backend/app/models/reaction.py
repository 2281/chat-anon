import uuid

from sqlalchemy import BigInteger, ForeignKey, Identity, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Reaction(Base):
    __tablename__ = "reactions"
    __table_args__ = (
        UniqueConstraint("message_id", "participant_token", name="uq_reaction_message_participant"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    message_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("messages.id", ondelete="CASCADE"), index=True
    )
    participant_token: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("participants.token", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(8))  # like | dislike

    message: Mapped["Message"] = relationship(back_populates="reactions")
