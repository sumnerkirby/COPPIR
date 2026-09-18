"""The decision log."""
import uuid
from datetime import datetime

from fastapi import APIRouter

from models import LogEntry
from state import broadcast, decision_log

router = APIRouter()

@router.get("/api/log")
async def get_log():
    return decision_log

@router.post("/api/log", status_code=201)
async def add_log(entry: LogEntry):
    rec = {**entry.model_dump(), "id": str(uuid.uuid4()),
           "timestamp": datetime.now().isoformat(), "auto": False}
    decision_log.append(rec)
    await broadcast({"type": "log_entry", "entry": rec})
    return rec
