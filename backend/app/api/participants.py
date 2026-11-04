import secrets

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_participant, get_db
from app.models import Participant
from app.schemas.participants import ParticipantCreate, ParticipantOut, ParticipantUpdate

router = APIRouter(prefix="/api/participants", tags=["participants"])


def _generate_anon_nickname() -> str:
    return f"анон-{secrets.randbelow(9_000_000) + 1_000_000}"


async def _find_by_email(db: AsyncSession, email: str) -> Participant | None:
    return await db.scalar(select(Participant).where(Participant.email == email))


@router.post("", response_model=ParticipantOut)
async def register(
    data: ParticipantCreate,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> Participant:
    # идентичность — по email: повторный вход выдаёт существующую запись (тот же token),
    # независимо от введённого никнейма; никнейм обновляется, только если введён непустой
    email = data.email.lower()
    nickname = data.nickname.strip() if data.nickname else ""

    participant = await _find_by_email(db, email)
    if participant is not None:
        if nickname and nickname != participant.nickname:
            participant.nickname = nickname
            await db.commit()
        return participant

    participant = Participant(email=email, nickname=nickname or _generate_anon_nickname())
    db.add(participant)
    try:
        await db.commit()
    except IntegrityError:
        # гонка: параллельный запрос уже создал запись с этим email
        await db.rollback()
        participant = await _find_by_email(db, email)
        if participant is None:  # не гонка, а иное нарушение целостности — пробрасываем
            raise
        return participant
    await db.refresh(participant)
    response.status_code = status.HTTP_201_CREATED
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
