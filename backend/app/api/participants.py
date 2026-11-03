import secrets

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_participant, get_db
from app.models import Participant
from app.schemas.participants import ParticipantCreate, ParticipantOut, ParticipantUpdate

router = APIRouter(prefix="/api/participants", tags=["participants"])


def _generate_anon_nickname() -> str:
    return f"анон-{secrets.randbelow(9_000_000) + 1_000_000}"


@router.post("", response_model=ParticipantOut, status_code=status.HTTP_201_CREATED)
async def register(data: ParticipantCreate, db: AsyncSession = Depends(get_db)) -> Participant:
    nickname = data.nickname.strip() if data.nickname else ""
    participant = Participant(nickname=nickname or _generate_anon_nickname())
    db.add(participant)
    await db.commit()
    await db.refresh(participant)
    return participant


@router.get("/me", response_model=ParticipantOut)
async def me(participant: Participant = Depends(get_current_participant)) -> Participant:
    return participant


@router.patch("/me", response_model=ParticipantOut)
async def update_me(
    data: ParticipantUpdate,
    participant: Participant = Depends(get_current_participant),
    db: AsyncSession = Depends(get_db),
) -> Participant:
    if data.nickname is not None:
        nickname = data.nickname.strip()
        if nickname:
            participant.nickname = nickname
            await db.commit()
    return participant
