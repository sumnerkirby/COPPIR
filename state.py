"""In-memory application state, and the helper that pushes it to clients.

There is no database. Everything here lives for the duration of a session and
is persisted only when someone saves a scenario. Modules import these
containers by name and mutate them in place -- nothing rebinds them, which is
what keeps every importer looking at the same objects.
"""
from typing import Dict, List

from fastapi import WebSocket

pins: Dict[str, dict] = {}
injects: Dict[str, dict] = {}
edges: Dict[str, dict] = {}
thresholds: List[dict] = []
decision_log: List[dict] = []
clients: set[WebSocket] = set()


async def broadcast(msg: dict):
    dead = set()
    for ws in clients:
        try:
            await ws.send_json(msg)
        except Exception:
            dead.add(ws)
    clients.difference_update(dead)
