from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import async_session
from app.models import Participant


async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session


async def get_current_participant(
    db: Annotated[AsyncSession, Depends(get_db)],
    x_participant_token: Annotated[UUID | None, Header()] = None,
) -> Participant:
    participant = await get_current_participant_optional(db, x_participant_token)
    if participant is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "отсутствует или неверен заголовок X-Participant-Token")
    return participant


async def get_current_participant_optional(
    db: Annotated[AsyncSession, Depends(get_db)],
    x_participant_token: Annotated[UUID | None, Header()] = None,
) -> Participant | None:
    """Участник по токену, если заголовок передан и валиден; иначе None (для публичных эндпоинтов)."""
    if x_participant_token is None:
        return None
    return await db.get(Participant, x_participant_token)
