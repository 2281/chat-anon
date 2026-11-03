from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ParticipantCreate(BaseModel):
    nickname: str | None = Field(default=None, max_length=64)


class ParticipantUpdate(BaseModel):
    nickname: str | None = Field(default=None, max_length=64)


class ParticipantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    token: UUID
    nickname: str
