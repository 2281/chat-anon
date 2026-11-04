from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_participant, get_current_participant_optional, get_db
from app.models import Participant
from app.schemas.messages import MessageCreate, MessageOut, MessagePage, MessageUpdate, ReactionSet
from app.services import conversations as conversation_service
from app.services import messages as message_service
from app.services import notifications as notification_service
from app.storage.s3 import delete_object
from app.ws.manager import manager

router = APIRouter(prefix="/api/messages", tags=["messages"])


async def _broadcast_reaction_update(
    db: AsyncSession, message: MessageOut, conversation_id: int | None
) -> None:
    data = {"message_id": message.id, "likes": message.likes, "dislikes": message.dislikes}
    if conversation_id is not None:
        # реакции в личке — только участникам диалога
        data["conversation_id"] = conversation_id
        tokens = await conversation_service.member_tokens(db, conversation_id)
        await manager.send_to_tokens(tokens, "dm.reaction", data)
    else:
        await manager.broadcast("message.reaction", data)


@router.post("", response_model=MessageOut, status_code=status.HTTP_201_CREATED)
async def create_message(
    data: MessageCreate,
    db: AsyncSession = Depends(get_db),
    participant: Participant = Depends(get_current_participant),
) -> MessageOut:
    message = await message_service.create_message(db, participant, data)
    payload = MessageOut.model_validate(message)
    await manager.broadcast("message.new", payload.model_dump(mode="json"))
    # уведомления автору родителя и участникам ветки; recipient_token в payload —
    # клиент показывает только свои (WS-канал общий, без аутентификации)
    notifications = await notification_service.create_reply_notifications(db, message)
    for notification in notifications:
        data_out = notification_service.to_out(notification).model_dump(mode="json")
        data_out["recipient_token"] = str(notification.participant_token)
        await manager.broadcast("notification.new", data_out)
    return payload


@router.get("", response_model=MessagePage)
async def list_messages(
    db: AsyncSession = Depends(get_db),
    participant: Participant | None = Depends(get_current_participant_optional),
    before_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=50, ge=1, le=100),
) -> MessagePage:
    roots, next_cursor = await message_service.list_messages(db, before_id, limit)
    if participant is not None:
        # реакции проставляем и корням, и всем ответам в ветках
        all_messages = [m for root in roots for m in (root, *root.replies)]
        await message_service.attach_my_reactions(db, all_messages, participant.token)
    return MessagePage(items=[MessageOut.model_validate(m) for m in roots], next_cursor=next_cursor)


@router.patch("/{message_id}", response_model=MessageOut)
async def update_message(
    message_id: int,
    data: MessageUpdate,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    participant: Participant = Depends(get_current_participant),
) -> MessageOut:
    """Редактирование своего сообщения: текст и полный желаемый набор вложений."""
    message, removed_keys = await message_service.update_message(db, participant, message_id, data)
    payload = MessageOut.model_validate(message)
    event_data = payload.model_dump(mode="json")
    if message.conversation_id is not None:
        # события лички не уходят в общий broadcast
        event_data["conversation_id"] = message.conversation_id
        tokens = await conversation_service.member_tokens(db, message.conversation_id)
        await manager.send_to_tokens(tokens, "dm.updated", event_data)
    else:
        await manager.broadcast("message.updated", event_data)
    # файлы отсоединённых вложений убираем после ответа клиенту
    for key in removed_keys:
        background.add_task(delete_object, key)
    return payload


@router.delete("/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_message(
    message_id: int,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    participant: Participant = Depends(get_current_participant),
) -> Response:
    """Удаление своего сообщения (только автор). В общем чате событие уходит всем,
    в личке — только участникам диалога."""
    keys, conversation_id = await message_service.delete_message(db, participant, message_id)
    if conversation_id is not None:
        tokens = await conversation_service.member_tokens(db, conversation_id)
        await manager.send_to_tokens(
            tokens, "dm.deleted", {"conversation_id": conversation_id, "message_id": message_id}
        )
    else:
        await manager.broadcast("message.deleted", {"message_id": message_id})
    # файлы из хранилища убираем после ответа клиенту
    for key in keys:
        background.add_task(delete_object, key)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{message_id}/reactions", response_model=MessageOut)
async def set_reaction(
    message_id: int,
    data: ReactionSet,
    db: AsyncSession = Depends(get_db),
    participant: Participant = Depends(get_current_participant),
) -> MessageOut:
    prev_kind = await message_service.get_reaction_kind(db, participant, message_id)
    message = await message_service.set_reaction(db, participant, message_id, data.kind)
    setattr(message, "my_reaction", data.kind)
    payload = MessageOut.model_validate(message)
    await _broadcast_reaction_update(db, payload, message.conversation_id)
    # уведомления об оценках — только для общего чата; в личке счётчик непрочитанных
    if message.conversation_id is None and prev_kind != data.kind:
        # смена реакции: старое уведомление снимаем, новое создаём автору сообщения
        if prev_kind is not None:
            await notification_service.remove_reaction_notification(db, participant, message, prev_kind)
        notification = await notification_service.create_reaction_notification(
            db, participant, message, data.kind
        )
        if notification is not None:
            data_out = notification_service.to_out(notification).model_dump(mode="json")
            data_out["recipient_token"] = str(notification.participant_token)
            await manager.broadcast("notification.new", data_out)
    return payload


@router.delete("/{message_id}/reactions/me", response_model=MessageOut)
async def remove_reaction(
    message_id: int,
    db: AsyncSession = Depends(get_db),
    participant: Participant = Depends(get_current_participant),
) -> MessageOut:
    prev_kind = await message_service.get_reaction_kind(db, participant, message_id)
    message = await message_service.remove_reaction(db, participant, message_id)
    if message.conversation_id is None and prev_kind is not None:
        await notification_service.remove_reaction_notification(db, participant, message, prev_kind)
    payload = MessageOut.model_validate(message)
    await _broadcast_reaction_update(db, payload, message.conversation_id)
    return payload
