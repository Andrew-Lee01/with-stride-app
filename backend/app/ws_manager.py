from collections import defaultdict
from typing import Dict, List

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._rooms: Dict[int, List[WebSocket]] = defaultdict(list)

    async def connect(self, session_id: int, ws: WebSocket) -> None:
        await ws.accept()
        self._rooms[session_id].append(ws)

    def disconnect(self, session_id: int, ws: WebSocket) -> None:
        if ws in self._rooms[session_id]:
            self._rooms[session_id].remove(ws)

    async def broadcast(self, session_id: int, payload: dict) -> None:
        dead = []
        for ws in self._rooms.get(session_id, []):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(session_id, ws)


manager = ConnectionManager()
