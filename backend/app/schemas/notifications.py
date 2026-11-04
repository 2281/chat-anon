from datetime import datetime

from pydantic import BaseModel


class NotificationOut(BaseModel):
    id: int
    # сообщение, к которому ведёт уведомление (ответ / оценённое)
    message_id: int
    # reply | like | dislike
    kind: str
    actor_nickname: str
    excerpt: str
    is_read: bool
    created_at: datetime
