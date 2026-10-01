from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Dict, List, Any
import json
import uuid

router = APIRouter(
    prefix="/gestio/ws",
    tags=["WebSocket Telemetry"]
)

class ConnectionManager:
    def __init__(self):
        # empresa_id -> list of WebSockets
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, empresa_id: str):
        await websocket.accept()
        if empresa_id not in self.active_connections:
            self.active_connections[empresa_id] = []
        self.active_connections[empresa_id].append(websocket)

    def disconnect(self, websocket: WebSocket, empresa_id: str):
        if empresa_id in self.active_connections:
            try:
                self.active_connections[empresa_id].remove(websocket)
                if not self.active_connections[empresa_id]:
                    del self.active_connections[empresa_id]
            except ValueError:
                pass

    async def broadcast(self, empresa_id: str, message: dict):
        if empresa_id in self.active_connections:
            for connection in self.active_connections[empresa_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    pass

manager = ConnectionManager()

@router.websocket("")
async def websocket_endpoint(
    websocket: WebSocket,
    empresa_id: str = Query(...)
):
    await manager.connect(websocket, empresa_id)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                # Broadcast back to the same empresa_id
                await manager.broadcast(empresa_id, message)
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        manager.disconnect(websocket, empresa_id)

