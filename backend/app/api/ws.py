import uuid

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.db import async_session
from app.models import Participant
from app.ws.manager import manager

router = APIRouter()


@router.websocket("/ws/chat")
async def chat_websocket(
    websocket: WebSocket, token: uuid.UUID | None = Query(default=None)
) -> None:
    # токен связывает подключение с участником для таргетированных событий (личка);
    # неизвестный токен — подключение остаётся анонимным (только общий broadcast)
    if token is not None:
        async with async_session() as session:
            if await session.get(Participant, token) is None:
                token = None
    await manager.connect(websocket, token)
    try:
        while True:
            # клиенты только получают события; цикл чтения нужен,
            # чтобы своевременно замечать закрытие соединения
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket)
