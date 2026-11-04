from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.models import Attachment, Message, Participant, Reaction
from app.schemas.messages import MessageCreate, MessageUpdate

# жадная загрузка всего, что нужно для сериализации MessageOut
_MESSAGE_LOAD = (selectinload(Message.attachments), joinedload(Message.participant))


async def _ensure_message_exists(db: AsyncSession, message_id: int) -> None:
    result = await db.execute(select(Message.id).where(Message.id == message_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"сообщение {message_id} не найдено")


async def _reload_message(db: AsyncSession, message_id: int) -> Message:
    result = await db.execute(select(Message).options(*_MESSAGE_LOAD).where(Message.id == message_id))
    return result.scalar_one()


async def _claim_attachments(db: AsyncSession, attachment_ids: list[int]) -> list[Attachment]:
    unique_ids = list(dict.fromkeys(attachment_ids))  # снять дубликаты, сохранив порядок
    result = await db.execute(
        select(Attachment).where(Attachment.id.in_(unique_ids), Attachment.message_id.is_(None))
    )
    attachments = list(result.scalars())
    if len(attachments) != len(unique_ids):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "вложения не найдены или уже прикреплены к другим сообщениям",
        )
    return attachments


async def create_message(
    db: AsyncSession, participant: Participant, data: MessageCreate
) -> Message:
    if data.reply_to_id is not None:
        await _ensure_message_exists(db, data.reply_to_id)
    if data.quote_message_id is not None:
        await _ensure_message_exists(db, data.quote_message_id)

    text = data.text.strip()
    attachments = await _claim_attachments(db, data.attachment_ids) if data.attachment_ids else []
    if not text and not attachments:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "сообщение не должно быть пустым")

    message = Message(
        participant_token=participant.token,
        text=text,
        reply_to_id=data.reply_to_id,
        quote_message_id=data.quote_message_id,
        quote_excerpt=data.quote_excerpt,
    )
    db.add(message)
    await db.flush()
    for attachment in attachments:
        attachment.message_id = message.id
    await db.commit()
    return await _reload_message(db, message.id)


async def list_messages(
    db: AsyncSession, before_id: int | None, limit: int
) -> tuple[list[Message], int | None]:
    """Страница корневых сообщений (не ответов), новые первыми.

    К каждому корню прикрепляет транзитный атрибут .replies — все потомки
    (ответы любой глубины) плоским списком по id ASC, для сериализации в MessageOut.
    """
    stmt = (
        select(Message)
        .options(*_MESSAGE_LOAD)
        .where(Message.reply_to_id.is_(None))
        .where(Message.conversation_id.is_(None))  # личка в общую ленту не попадает
        .order_by(Message.id.desc())
        .limit(limit + 1)
    )
    if before_id is not None:
        stmt = stmt.where(Message.id < before_id)
    roots = list((await db.execute(stmt)).scalars())

    next_cursor = None
    if len(roots) > limit:  # есть более ранняя история
        roots = roots[:limit]
        next_cursor = roots[-1].id

    # потомки корней страницы: итеративный обход по уровням (глубина веток мала)
    root_of = {root.id: root.id for root in roots}
    replies: dict[int, list[Message]] = {root.id: [] for root in roots}
    frontier = [root.id for root in roots]
    while frontier:
        children = list(
            (
                await db.execute(
                    select(Message)
                    .options(*_MESSAGE_LOAD)
                    .where(Message.reply_to_id.in_(frontier))
                    .order_by(Message.id)
                )
            ).scalars()
        )
        frontier = []
        for child in children:
            root_id = root_of[child.reply_to_id]
            root_of[child.id] = root_id
            replies[root_id].append(child)
            frontier.append(child.id)

    for root in roots:
        root_replies = sorted(replies[root.id], key=lambda m: m.id)
        for reply in root_replies:
            reply.replies = []
        root.replies = root_replies
    return roots, next_cursor


async def attach_my_reactions(
    db: AsyncSession, messages: list[Message], participant_token: Participant.token
) -> None:
    """Заполняет message.my_reaction реакциями указанного участника (in-place)."""
    if not messages:
        return
    result = await db.execute(
        select(Reaction.message_id, Reaction.kind).where(
            Reaction.participant_token == participant_token,
            Reaction.message_id.in_([m.id for m in messages]),
        )
    )
    kind_by_id = dict(result.all())
    for message in messages:
        message.my_reaction = kind_by_id.get(message.id)


async def get_reaction_kind(
    db: AsyncSession, participant: Participant, message_id: int
) -> str | None:
    """Текущая реакция участника на сообщение (для логики уведомлений об оценках)."""
    return await db.scalar(
        select(Reaction.kind).where(
            Reaction.message_id == message_id,
            Reaction.participant_token == participant.token,
        )
    )


async def set_reaction(
    db: AsyncSession, participant: Participant, message_id: int, kind: str
) -> Message:
    await _ensure_message_exists(db, message_id)
    result = await db.execute(
        select(Reaction).where(
            Reaction.message_id == message_id, Reaction.participant_token == participant.token
        )
    )
    reaction = result.scalar_one_or_none()
    if reaction is None:
        db.add(
            Reaction(message_id=message_id, participant_token=participant.token, kind=kind)
        )
    else:
        reaction.kind = kind
    await db.commit()
    return await _reload_message(db, message_id)


async def remove_reaction(
    db: AsyncSession, participant: Participant, message_id: int
) -> Message:
    await _ensure_message_exists(db, message_id)
    result = await db.execute(
        select(Reaction).where(
            Reaction.message_id == message_id, Reaction.participant_token == participant.token
        )
    )
    reaction = result.scalar_one_or_none()
    if reaction is not None:
        await db.delete(reaction)
        await db.commit()
    return await _reload_message(db, message_id)


async def delete_message(
    db: AsyncSession, participant: Participant, message_id: int
) -> tuple[list[str], int | None]:
    """Удаляет сообщение автора. Возвращает s3-ключи вложений и id диалога (None — общий чат).

    Ответы и цитаты на это сообщение сохраняются — их FK обнуляются (SET NULL).
    """
    result = await db.execute(select(Message).where(Message.id == message_id))
    message = result.scalar_one_or_none()
    if message is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"сообщение {message_id} не найдено")
    if message.participant_token != participant.token:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "удалять можно только свои сообщения")

    keys = list(
        (await db.execute(select(Attachment.s3_key).where(Attachment.message_id == message_id)))
        .scalars()
    )
    conversation_id = message.conversation_id
    await db.delete(message)
    await db.commit()
    return keys, conversation_id


async def update_message(
    db: AsyncSession, participant: Participant, message_id: int, data: MessageUpdate
) -> tuple[Message, list[str]]:
    """Редактирует текст и набор вложений (только автор).

    attachment_ids — полный желаемый набор: текущие + новые идут списком,
    вложения, которых в списке нет, отсоединяются (и чистятся из хранилища).
    Возвращает сообщение и s3-ключи отсоединённых вложений.
    """
    result = await db.execute(select(Message).where(Message.id == message_id))
    message = result.scalar_one_or_none()
    if message is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"сообщение {message_id} не найдено")
    if message.participant_token != participant.token:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "редактировать можно только свои сообщения")

    text = data.text.strip()
    wanted_ids = list(dict.fromkeys(data.attachment_ids))

    current = list(
        (await db.execute(select(Attachment).where(Attachment.message_id == message_id))).scalars()
    )
    current_by_id = {a.id: a for a in current}

    new_ids = [i for i in wanted_ids if i not in current_by_id]
    new_attachments: list[Attachment] = []
    if new_ids:
        result = await db.execute(
            select(Attachment).where(Attachment.id.in_(new_ids), Attachment.message_id.is_(None))
        )
        new_attachments = list(result.scalars())
        found_ids = {a.id for a in new_attachments}
        missing = [i for i in new_ids if i not in found_ids]
        if missing:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"вложения не найдены или уже заняты: {missing}",
            )

    if not text and not wanted_ids:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "сообщение не должно быть пустым")

    removed_keys: list[str] = []
    for attachment in current:
        if attachment.id not in wanted_ids:
            removed_keys.append(attachment.s3_key)
            await db.delete(attachment)
    for attachment in new_attachments:
        attachment.message_id = message_id

    message.text = text
    message.edited_at = datetime.now(timezone.utc)
    await db.commit()
    return await _reload_message(db, message.id), removed_keys
