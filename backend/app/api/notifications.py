from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_participant, get_db
from app.models import Participant
from app.schemas.notifications import NotificationOut
from app.services import notifications as notification_service

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
async def list_notifications(
    db: AsyncSession = Depends(get_db),
    participant: Participant = Depends(get_current_participant),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[NotificationOut]:
    """Все уведомления участника (новые и старые), новые первыми."""
    notifications = await notification_service.list_notifications(db, participant.token, limit)
    return [notification_service.to_out(n) for n in notifications]


@router.post("/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_read(
    notification_id: int,
    db: AsyncSession = Depends(get_db),
    participant: Participant = Depends(get_current_participant),
) -> None:
    """Пометить уведомление прочитанным (по клику на нём)."""
    if not await notification_service.mark_read(db, participant.token, notification_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "уведомление не найдено")
