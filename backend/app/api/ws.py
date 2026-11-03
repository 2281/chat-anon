from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.ws.manager import manager

router = APIRouter()


@router.websocket("/ws/chat")
async def chat_websocket(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        while True:
            # клиенты только получают события; цикл чтения нужен,
            # чтобы своевременно замечать закрытие соединения
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket)
