"""The websocket every client holds open for live updates."""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from state import clients, decision_log, edges, injects, pins, thresholds

router = APIRouter()

@router.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    clients.add(ws)
    await ws.send_json({"type": "full_state", "pins": pins,
                        "injects": list(injects.values()), "edges": list(edges.values()),
                        "thresholds": thresholds, "log": decision_log})
    try:
        # Loop is required to keep the connection open; the server only pushes,
        # so incoming frames are discarded. WebSocketDisconnect is raised by
        # Starlette when the client closes the connection cleanly or drops.
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        clients.discard(ws)
