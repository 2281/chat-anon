import uuid

from fastapi import WebSocket, WebSocketDisconnect


class ConnectionManager:
    """Активные WebSocket-подключения и рассылка событий.

    Подключение может быть связано с токеном участника — тогда ему доступна
    таргетированная доставка (личные сообщения). Общий broadcast получают все.
    Один инстанс в памяти процесса — корректно для одного запущенного backend.
    При горизонтальном масштабировании сюда добавится общий брокер (например, Redis pub/sub).
    """

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._token_of: dict[WebSocket, str] = {}
        self._by_token: dict[str, set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, token: uuid.UUID | None = None) -> None:
        await websocket.accept()
        self._connections.add(websocket)
        if token is not None:
            key = str(token)
            self._token_of[websocket] = key
            self._by_token.setdefault(key, set()).add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)
        key = self._token_of.pop(websocket, None)
        if key is not None:
            sockets = self._by_token.get(key)
            if sockets is not None:
                sockets.discard(websocket)
                if not sockets:
                    del self._by_token[key]

    async def broadcast(self, event: str, data: dict) -> None:
        await self._send(self._connections, event, data)

    async def send_to_tokens(self, tokens: list[uuid.UUID], event: str, data: dict) -> None:
        targets: set[WebSocket] = set()
        for token in tokens:
            targets |= self._by_token.get(str(token), set())
        await self._send(targets, event, data)

    async def _send(self, targets, event: str, data: dict) -> None:
        dead: list[WebSocket] = []
        for websocket in targets:
            try:
                await websocket.send_json({"event": event, "data": data})
            except (WebSocketDisconnect, RuntimeError):
                # RuntimeError — попытка отправки по закрытому соединению
                dead.append(websocket)
        for websocket in dead:
            self.disconnect(websocket)


manager = ConnectionManager()
