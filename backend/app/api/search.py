from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_participant, get_db
from app.models import Participant
from app.schemas.messages import MessageOut, SearchHit, SearchResults
from app.services import messages as message_service

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("/messages", response_model=SearchResults)
async def search_messages(
    q: str = Query(min_length=1, max_length=200),
    limit: int = Query(default=30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    participant=Depends(get_current_participant),
) -> SearchResults:
    """Поиск по общему чату и личным диалогам участника (FTS + триграммы)."""
    messages = await message_service.search_messages(db, participant, q, limit)
    await message_service.attach_my_reactions(db, messages, participant.token)
    return SearchResults(
        items=[
            SearchHit(
                conversation_id=m.conversation_id,
                message=MessageOut.model_validate(m),
            )
            for m in messages
        ]
    )
