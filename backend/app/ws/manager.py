from fastapi import WebSocket, WebSocketDisconnect


class ConnectionManager:
    """Активные WebSocket-подключения и рассылка событий.

    Один инстанс в памяти процесса — корректно для одного запущенного backend.
    При горизонтальном масштабировании сюда добавится общий брокер (например, Redis pub/sub).
    """

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)

    async def broadcast(self, event: str, data: dict) -> None:
        dead: list[WebSocket] = []
        for websocket in self._connections:
            try:
                await websocket.send_json({"event": event, "data": data})
            except (WebSocketDisconnect, RuntimeError):
                # RuntimeError — попытка отправки по закрытому соединению
                dead.append(websocket)
        for websocket in dead:
            self.disconnect(websocket)


manager = ConnectionManager()
