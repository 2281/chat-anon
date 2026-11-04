import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_participant, get_db
from app.models import Participant
from app.schemas.conversations import (
    ConversationCreate,
    ConversationOut,
    DmMessageCreate,
    DmMessagePage,
    ReadMark,
)
from app.schemas.messages import MessageOut
from app.services import conversations as conversation_service
from app.services import messages as message_service
from app.ws.manager import manager

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.post("", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    data: ConversationCreate,
    db: AsyncSession = Depends(get_db),
    participant: Participant = Depends(get_current_participant),
) -> ConversationOut:
    """Открыть (или найти существующий) личный диалог с участником."""
    conversation = await conversation_service.find_or_create_dm(
        db, participant, data.participant_token
    )
    return await _conversation_out(db, participant, conversation.id)


@router.get("", response_model=list[ConversationOut])
async def list_conversations(
    db: AsyncSession = Depends(get_db),
    participant: Participant = Depends(get_current_participant),
) -> list[ConversationOut]:
    rows = await conversation_service.list_conversations(db, participant)
    return [
        ConversationOut(
            id=member.conversation_id,
            peer_token=peer.token,
            peer_nickname=peer.nickname,
            last_message=MessageOut.model_validate(last) if last is not None else None,
            unread_count=unread,
        )
        for member, peer, last, unread in rows
    ]


@router.get("/{conversation_id}/messages", response_model=DmMessagePage)
async def list_dm_messages(
    conversation_id: int,
    db: AsyncSession = Depends(get_db),
    participant: Participant = Depends(get_current_participant),
    before_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=50, ge=1, le=100),
) -> DmMessagePage:
    await conversation_service.get_member(db, conversation_id, participant.token)
    messages, next_cursor = await conversation_service.list_dm_messages(
        db, conversation_id, before_id, limit
    )
    await message_service.attach_my_reactions(db, messages, participant.token)
    return DmMessagePage(
        items=[MessageOut.model_validate(m) for m in messages], next_cursor=next_cursor
    )


@router.post(
    "/{conversation_id}/messages",
    response_model=MessageOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_dm_message(
    conversation_id: int,
    data: DmMessageCreate,
    db: AsyncSession = Depends(get_db),
    participant: Participant = Depends(get_current_participant),
) -> MessageOut:
    member = await conversation_service.get_member(db, conversation_id, participant.token)
    message = await conversation_service.create_dm_message(db, participant, conversation_id, data)
    payload = MessageOut.model_validate(message)
    event_data = payload.model_dump(mode="json")
    event_data["conversation_id"] = conversation_id
    # событие только участникам диалога — в общий broadcast личка не уходит
    tokens = await conversation_service.member_tokens(db, member.conversation_id)
    await manager.send_to_tokens(tokens, "dm.new", event_data)
    return payload


@router.post("/{conversation_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_read(
    conversation_id: int,
    data: ReadMark,
    db: AsyncSession = Depends(get_db),
    participant: Participant = Depends(get_current_participant),
) -> Response:
    member = await conversation_service.get_member(db, conversation_id, participant.token)
    await conversation_service.mark_read(db, member, data.last_read_message_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _conversation_out(
    db: AsyncSession, me: Participant, conversation_id: int
) -> ConversationOut:
    """ConversationOut одного диалога через общий список (диалогов у пользователя мало)."""
    for member, peer, last, unread in await conversation_service.list_conversations(db, me):
        if member.conversation_id == conversation_id:
            return ConversationOut(
                id=member.conversation_id,
                peer_token=peer.token,
                peer_nickname=peer.nickname,
                last_message=MessageOut.model_validate(last) if last is not None else None,
                unread_count=unread,
            )
    # диалог только что создан — membership гарантирован find_or_create_dm
    raise AssertionError(f"членство в диалоге {conversation_id} не найдено")
