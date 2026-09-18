"""Alert thresholds watching sector integrity."""
import uuid

from fastapi import APIRouter, HTTPException

from models import ThresholdIn
from state import broadcast, thresholds

router = APIRouter()

@router.get("/api/thresholds")
async def get_thresholds():
    return thresholds

@router.post("/api/thresholds", status_code=201)
async def create_threshold(t: ThresholdIn):
    rec = {**t.model_dump(), "id": str(uuid.uuid4())}
    thresholds.append(rec)
    await broadcast({"type": "threshold_add", "threshold": rec})
    return rec

@router.delete("/api/thresholds/{tid}")
async def delete_threshold(tid: str):
    for i, t in enumerate(thresholds):
        if t["id"] == tid:
            thresholds.pop(i)
            await broadcast({"type": "threshold_delete", "tid": tid})
            return {"ok": True}
    raise HTTPException(404)
