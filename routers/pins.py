"""Pins: the assets, responders and points of interest on the map."""
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException

from models import BulkCreate, BulkStatusReq, PinIn, PinUpdate
from state import broadcast, edges, pins

router = APIRouter()

@router.get("/api/pins")
async def get_pins():
    return pins

@router.post("/api/pins", status_code=201)
async def create_pin(pin: PinIn):
    pid = str(uuid.uuid4())
    now = datetime.now().isoformat()
    pins[pid] = {**pin.model_dump(), "id": pid, "pinned_at": now,
                 "status_history": [{"status": pin.status, "timestamp": now}]}
    await broadcast({"type": "pin_add", "pin": pins[pid]})
    return pins[pid]

@router.post("/api/pins/bulk", status_code=201)
async def bulk_create(body: BulkCreate):
    created = []
    for it in body.items:
        pid = str(uuid.uuid4())
        now = datetime.now().isoformat()
        pins[pid] = {**it.model_dump(), "id": pid, "status": body.status,
                     "op_status": body.op_status, "pin_color": body.pin_color,
                     "notes": "", "pinned_at": now,
                     "status_history": [{"status": body.status, "timestamp": now}]}
        created.append(pins[pid])
    await broadcast({"type": "bulk_add", "pins": created})
    return created

@router.put("/api/pins/{pid}")
async def update_pin(pid: str, upd: PinUpdate):
    if pid not in pins:
        raise HTTPException(404, "Pin not found")
    for k, v in upd.model_dump().items():
        if v is not None:
            if k == "status" and pins[pid].get("status") != v:
                pins[pid].setdefault("status_history", []).append(
                    {"status": v, "timestamp": datetime.now().isoformat()})
            pins[pid][k] = v
    await broadcast({"type": "pin_update", "pin": pins[pid]})
    return pins[pid]

@router.delete("/api/pins/{pid}")
async def delete_pin(pid: str):
    if pid not in pins:
        raise HTTPException(404, "Pin not found")
    del pins[pid]
    # An edge cannot outlive either of the pins it joins. Clients drop these
    # locally on pin_delete, but the server has to as well or they survive in
    # every later full_state and get written into saved scenarios.
    for eid in [eid for eid, e in edges.items()
                if e["from_pid"] == pid or e["to_pid"] == pid]:
        del edges[eid]
    await broadcast({"type": "pin_delete", "pid": pid})
    return {"ok": True}

@router.delete("/api/pins")
async def clear_pins():
    pids = list(pins.keys())
    pins.clear()
    edges.clear()
    await broadcast({"type": "pins_cleared", "pids": pids})
    return {"ok": True, "count": len(pids)}

@router.post("/api/pins/bulk-status")
async def bulk_status(req: BulkStatusReq):
    updated = []
    for pin in pins.values():
        if req.category is None or pin.get("category") == req.category:
            if req.status and pin.get("status") != req.status:
                pin.setdefault("status_history", []).append(
                    {"status": req.status, "timestamp": datetime.now().isoformat()})
            if req.status:    pin["status"]    = req.status
            if req.op_status: pin["op_status"] = req.op_status
            updated.append(pin)
    await broadcast({"type": "bulk_update", "pins": updated})
    return {"ok": True, "count": len(updated)}
