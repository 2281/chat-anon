import uuid

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models import Message, Notification, Participant
from app.schemas.notifications import NotificationOut


def _excerpt(message: Message) -> str:
    text = message.text.strip()
    if not text:
        return "[вложение]"
    return text[:100] + ("…" if len(text) > 100 else "")


def to_out(notification: Notification) -> NotificationOut:
    # у записей без actor (до появления колонки) — подставляем автора сообщения
    actor = notification.actor or notification.message.participant
    return NotificationOut(
        id=notification.id,
        message_id=notification.message_id,
        kind=notification.kind,
        actor_nickname=actor.nickname,
        excerpt=_excerpt(notification.message),
        is_read=notification.is_read,
        created_at=notification.created_at,
    )


async def create_reply_notifications(db: AsyncSession, reply: Message) -> list[Notification]:
    """Создаёт уведомления о новом ответе.

    Получатели — все авторы ветки (корень + все потомки), кроме автора ответа:
    и тот, чьё сообщение процитировано ответом, и участники ветки целиком.
    Вызывается после commit сообщения; commit уведомлений — на стороне вызова.
    """
    if reply.reply_to_id is None:
        return []

    # поднимаемся к корню ветки по цепочке reply_to_id
    root_id = reply.reply_to_id
    while True:
        parent_reply_to = await db.scalar(
            select(Message.reply_to_id).where(Message.id == root_id)
        )
        if parent_reply_to is None:
            break
        root_id = parent_reply_to

    # авторы корня и всех потомков (обход по уровням)
    tokens: set[uuid.UUID] = set()
    root_author = await db.scalar(select(Message.participant_token).where(Message.id == root_id))
    if root_author is not None:
        tokens.add(root_author)
    frontier = [root_id]
    while frontier:
        rows = await db.execute(
            select(Message.id, Message.participant_token).where(Message.reply_to_id.in_(frontier))
        )
        frontier = []
        for msg_id, token in rows:
            tokens.add(token)
            frontier.append(msg_id)

    tokens.discard(reply.participant_token)
    notifications = [
        Notification(
            participant_token=token,
            message_id=reply.id,
            kind="reply",
            actor_token=reply.participant_token,
        )
        for token in tokens
    ]
    db.add_all(notifications)
    await db.commit()
    for notification in notifications:
        notification.message = reply  # для сериализации без повторного запроса
        notification.actor = reply.participant
    return notifications


async def create_reaction_notification(
    db: AsyncSession, reactor: Participant, message: Message, kind: str
) -> Notification | None:
    """Уведомление автору сообщения об оценке (like/dislike).

    Без дублей: повторная та же оценка того же участника не создаёт новое
    уведомление. Свою оценку снимает remove_reaction_notification.
    """
    if message.participant_token == reactor.token:
        return None
    existing = await db.scalar(
        select(Notification.id).where(
            Notification.participant_token == message.participant_token,
            Notification.actor_token == reactor.token,
            Notification.message_id == message.id,
            Notification.kind == kind,
        )
    )
    if existing is not None:
        return None
    notification = Notification(
        participant_token=message.participant_token,
        message_id=message.id,
        kind=kind,
        actor_token=reactor.token,
    )
    db.add(notification)
    await db.commit()
    notification.message = message  # для сериализации без повторного запроса
    notification.actor = reactor
    return notification


async def remove_reaction_notification(
    db: AsyncSession, reactor: Participant, message: Message, kind: str
) -> None:
    """Снимает уведомление об оценке, когда участник убрал/сменил реакцию."""
    await db.execute(
        delete(Notification).where(
            Notification.participant_token == message.participant_token,
            Notification.actor_token == reactor.token,
            Notification.message_id == message.id,
            Notification.kind == kind,
        )
    )
    await db.commit()


async def list_notifications(
    db: AsyncSession, participant_token: uuid.UUID, limit: int = 100
) -> list[Notification]:
    """Уведомления участника, новые первыми."""
    result = await db.execute(
        select(Notification)
        .options(
            joinedload(Notification.message).joinedload(Message.participant),
            joinedload(Notification.actor),
        )
        .where(Notification.participant_token == participant_token)
        .order_by(Notification.id.desc())
        .limit(limit)
    )
    return list(result.scalars().unique())


async def mark_read(db: AsyncSession, participant_token: uuid.UUID, notification_id: int) -> bool:
    """Помечает уведомление прочитанным (по клику). False — не найдено/чужое."""
    result = await db.execute(
        update(Notification)
        .where(
            Notification.id == notification_id,
            Notification.participant_token == participant_token,
        )
        .values(is_read=True)
    )
    await db.commit()
    return result.rowcount > 0
