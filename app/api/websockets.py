import json
import logging
from typing import List
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status, Cookie
from jose import jwt, JWTError

from app.core.config import settings
from app.core.security import ALGORITHM

ws_router = APIRouter()
logger = logging.getLogger("gym_sockets")
logger.setLevel(logging.INFO)

class ConnectionManager:
    """
    Maintains a pool of all actively connected gym staff and admin dashboards.
    Used to blast live attendance events directly to their monitors.
    """
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Socket Opened. Active Pool Count: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(f"Socket Dropped. Active Pool Count: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """ Fires a JSON payload to every active staff dashboard in ~5ms. """
        json_msg = json.dumps(message)
        for connection in self.active_connections:
            try:
                await connection.send_text(json_msg)
            except Exception as e:
                logger.error(f"Failed socket transmission: {e}")

manager = ConnectionManager()


@ws_router.websocket("/ws/dashboard")
async def live_dashboard_socket(
    websocket: WebSocket,
    access_token: str | None = Cookie(None)
):
    """ The WS Handshake pipeline. Strictly Protected by JWT. """
    
    # 1. Immediate termination if no Secure Cookie exists.
    if access_token is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # 2. Strict decoding to ensure the token isn't forged.
    try:
        payload = jwt.decode(access_token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if not user_id:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
    except JWTError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # 3. Connection is valid. Mount them to the broadcast pool.
    await manager.connect(websocket)
    try:
        while True:
            # We use this line to keep the connection alive indefinitely.
            # In our use-case, the client strictly receives; it doesn't send socket data back here.
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)