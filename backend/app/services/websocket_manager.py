import asyncio

from fastapi import WebSocket


class WebSocketManager:
    """A slow browser cannot block ingestion; each browser gets a bounded queue."""

    def __init__(self):
        self.clients: dict[WebSocket, asyncio.Queue] = {}
        self.dropped = 0

    async def register(self, socket: WebSocket) -> asyncio.Queue:
        await socket.accept()
        queue = asyncio.Queue(maxsize=32)
        self.clients[socket] = queue
        return queue

    def remove(self, socket: WebSocket) -> None:
        self.clients.pop(socket, None)

    def broadcast(self, message: dict) -> None:
        for queue in tuple(self.clients.values()):
            if queue.full():
                queue.get_nowait()
                self.dropped += 1
            queue.put_nowait(message)
