from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ParticipantCreate(BaseModel):
    # идентичность пользователя — по email; никнейм необязателен
    email: EmailStr = Field(max_length=255)
    nickname: str | None = Field(default=None, max_length=64)


class ParticipantUpdate(BaseModel):
    nickname: str | None = Field(default=None, max_length=64)


class ParticipantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    token: UUID
    nickname: str
