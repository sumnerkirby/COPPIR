"""Injects: pre-authored events a controller fires during an exercise."""
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException

from models import InjectIn
from state import broadcast, decision_log, injects, pins

router = APIRouter()

@router.get("/api/injects")
async def get_injects():
    return list(injects.values())

@router.post("/api/injects", status_code=201)
async def create_inject(inj: InjectIn):
    iid = str(uuid.uuid4())
    injects[iid] = {**inj.model_dump(), "id": iid,
                    "created_at": datetime.now().isoformat(), "triggered_at": None}
    await broadcast({"type": "inject_queued", "inject": injects[iid]})
    return injects[iid]

@router.delete("/api/injects/{iid}")
async def delete_inject(iid: str):
    if iid not in injects:
        raise HTTPException(404)
    del injects[iid]
    await broadcast({"type": "inject_delete", "iid": iid})
    return {"ok": True}

@router.post("/api/injects/{iid}/trigger")
async def trigger_inject(iid: str):
    if iid not in injects:
        raise HTTPException(404)
    inj = injects[iid]
    if inj.get("triggered_at"):
        # Firing twice would spawn a second copy of new_pin and write a second
        # log entry. The UI hides the button once fired, but a second window or
        # a double-click can still reach this.
        raise HTTPException(409, "Inject has already been triggered")
    now = datetime.now().isoformat()
    inj["triggered_at"] = now

    created_pin = None
    if inj.get("target_pid") and inj["target_pid"] in pins and inj.get("target_status"):
        tpid = inj["target_pid"]
        new_status = inj["target_status"]
        if pins[tpid].get("status") != new_status:
            pins[tpid].setdefault("status_history", []).append(
                {"status": new_status, "timestamp": now})
        pins[tpid]["status"] = new_status
    if inj.get("new_pin"):
        pid = str(uuid.uuid4())
        np = inj["new_pin"]
        st = np.get("status", "Under Investigation")
        pins[pid] = {**np, "id": pid, "pinned_at": now,
                     "pin_color": None, "notes": "", "status": st,
                     "status_history": [{"status": st, "timestamp": now}]}
        created_pin = pins[pid]

    entry = {
        "id": str(uuid.uuid4()), "timestamp": now,
        "action": f"INJECT TRIGGERED: {inj['title']}",
        "asset_name": pins.get(inj.get("target_pid", ""), {}).get("name"),
        "asset_pid": inj.get("target_pid"),
        "notes": inj["description"], "auto": True,
    }
    decision_log.append(entry)

    await broadcast({
        "type": "inject_triggered",
        "inject": inj,
        "log_entry": entry,
        "pins": pins,
        "new_pin": created_pin,
    })
    return inj
