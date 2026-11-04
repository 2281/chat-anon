import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.models import Attachment, Conversation, ConversationMember, Message, Participant
from app.schemas.conversations import DmMessageCreate
from app.services.messages import _MESSAGE_LOAD, _claim_attachments


async def get_member(
    db: AsyncSession, conversation_id: int, token: uuid.UUID
) -> ConversationMember:
    """Членство участника в диалоге или 404 (чужой диалог неотличим от несуществующего)."""
    member = await db.scalar(
        select(ConversationMember).where(
            ConversationMember.conversation_id == conversation_id,
            ConversationMember.participant_token == token,
        )
    )
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "диалог не найден")
    return member


async def find_or_create_dm(
    db: AsyncSession, me: Participant, peer_token: uuid.UUID
) -> Conversation:
    """Диалог двух участников: существующий или новый.

    Уникального индекса на пару нет — теоретическая гонка при одновременном
    создании с двух сторон может породить два диалога; для MVP пренебрегаем.
    """
    if peer_token == me.token:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "нельзя написать в лс самому себе")
    peer = await db.get(Participant, peer_token)
    if peer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "пользователь не найден")

    existing_id = await _find_dm_id(db, me.token, peer_token)
    if existing_id is not None:
        return await db.get(Conversation, existing_id)

    conversation = Conversation()
    db.add(conversation)
    await db.flush()
    db.add_all(
        [
            ConversationMember(conversation_id=conversation.id, participant_token=me.token),
            ConversationMember(conversation_id=conversation.id, participant_token=peer_token),
        ]
    )
    await db.commit()
    return conversation


async def _find_dm_id(db: AsyncSession, a: uuid.UUID, b: uuid.UUID) -> int | None:
    my = select(ConversationMember.conversation_id).where(
        ConversationMember.participant_token == a
    )
    return await db.scalar(
        select(ConversationMember.conversation_id)
        .where(ConversationMember.participant_token == b)
        .where(ConversationMember.conversation_id.in_(my))
        .limit(1)
    )


async def member_tokens(db: AsyncSession, conversation_id: int) -> list[uuid.UUID]:
    """Токены всех участников диалога — для таргетированной WS-доставки."""
    return list(
        (
            await db.execute(
                select(ConversationMember.participant_token).where(
                    ConversationMember.conversation_id == conversation_id
                )
            )
        ).scalars()
    )


async def peer_of(db: AsyncSession, conversation_id: int, my_token: uuid.UUID) -> Participant:
    """Собеседник в диалоге."""
    member = await db.scalar(
        select(ConversationMember).where(
            ConversationMember.conversation_id == conversation_id,
            ConversationMember.participant_token != my_token,
        )
    )
    return await db.get(Participant, member.participant_token)


async def list_conversations(
    db: AsyncSession, me: Participant
) -> list[tuple[ConversationMember, Participant, Message | None, int]]:
    """Мои диалоги: (моё членство, собеседник, последнее сообщение, непрочитанные)."""
    memberships = list(
        (
            await db.execute(
                select(ConversationMember).where(ConversationMember.participant_token == me.token)
            )
        ).scalars()
    )
    result = []
    for member in memberships:
        peer = await peer_of(db, member.conversation_id, me.token)
        last = await db.scalar(
            select(Message)
            .options(*_MESSAGE_LOAD)
            .where(Message.conversation_id == member.conversation_id)
            .order_by(Message.id.desc())
            .limit(1)
        )
        unread = await db.scalar(
            select(func.count(Message.id)).where(
                Message.conversation_id == member.conversation_id,
                Message.id > member.last_read_message_id,
                Message.participant_token != me.token,
            )
        )
        result.append((member, peer, last, unread or 0))
    # свежие диалоги сверху
    result.sort(
        key=lambda row: row[2].id if row[2] is not None else 0, reverse=True
    )
    return result


async def list_dm_messages(
    db: AsyncSession, conversation_id: int, before_id: int | None, limit: int
) -> tuple[list[Message], int | None]:
    stmt = (
        select(Message)
        .options(*_MESSAGE_LOAD)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.id.desc())
        .limit(limit + 1)
    )
    if before_id is not None:
        stmt = stmt.where(Message.id < before_id)
    messages = list((await db.execute(stmt)).scalars())
    next_cursor = None
    if len(messages) > limit:
        messages = messages[:limit]
        next_cursor = messages[-1].id
    return messages, next_cursor


async def create_dm_message(
    db: AsyncSession, me: Participant, conversation_id: int, data: DmMessageCreate
) -> Message:
    text = data.text.strip()
    attachments = await _claim_attachments(db, data.attachment_ids) if data.attachment_ids else []
    if not text and not attachments:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "сообщение не должно быть пустым")

    message = Message(
        participant_token=me.token,
        conversation_id=conversation_id,
        text=text,
    )
    db.add(message)
    await db.flush()
    for attachment in attachments:
        attachment.message_id = message.id
    await db.commit()
    result = await db.execute(
        select(Message).options(*_MESSAGE_LOAD).where(Message.id == message.id)
    )
    return result.scalar_one()


async def mark_read(
    db: AsyncSession, member: ConversationMember, last_read_message_id: int
) -> None:
    if last_read_message_id > member.last_read_message_id:
        member.last_read_message_id = last_read_message_id
        await db.commit()
