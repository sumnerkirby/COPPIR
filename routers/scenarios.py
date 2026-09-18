"""Saving, loading and clearing a session.

Scenario names reach the filesystem, so they are sanitised and the resolved
path is re-checked against the scenarios directory before anything is written.
"""
import json
import re
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException

import config
from models import ScenarioReq
from state import broadcast, decision_log, edges, injects, pins, thresholds

router = APIRouter()

def _state_payload() -> dict:
    return {"pins": pins, "injects": injects, "edges": edges,
            "thresholds": thresholds, "decision_log": decision_log,
            "saved_at": datetime.now().isoformat()}

def _safe_name(name: str) -> str:
    # Strip anything outside alphanumerics, hyphens, underscores, and spaces
    # so the result is safe as a filesystem filename on all platforms.
    return re.sub(r"[^a-zA-Z0-9_\- ]", "", name).strip()[:64]

@router.get("/api/scenarios")
async def list_scenarios():
    return sorted(f.stem for f in config.SCENARIOS_DIR.glob("*.json"))

def _scenario_path(name: str) -> Path:
    safe = _safe_name(name)
    if not safe:
        raise HTTPException(400, "Invalid scenario name")
    # Resolve symlinks and ".." components, then confirm the result still sits
    # inside the scenarios directory. This prevents path traversal via crafted names.
    path = (config.SCENARIOS_DIR / f"{safe}.json").resolve()
    if not str(path).startswith(str(config.SCENARIOS_DIR.resolve())):
        raise HTTPException(400, "Invalid scenario name")
    return path

@router.post("/api/scenarios/save")
async def save_scenario(req: ScenarioReq):
    path = _scenario_path(req.name)
    name = path.stem
    path.write_text(json.dumps({**_state_payload(), "name": name}, indent=2))
    return {"ok": True, "name": name}

@router.post("/api/scenarios/load")
async def load_scenario(req: ScenarioReq):
    path = _scenario_path(req.name)
    if not path.exists():
        raise HTTPException(404, f"Scenario not found")
    data = json.loads(path.read_text())
    pins.clear();         pins.update(data.get("pins", {}))
    injects.clear();      injects.update(data.get("injects", {}))
    edges.clear();        edges.update(data.get("edges", {}))
    thresholds.clear();   thresholds.extend(data.get("thresholds", []))
    decision_log.clear(); decision_log.extend(data.get("decision_log", []))
    await broadcast({"type": "full_state", "pins": pins,
                     "injects": list(injects.values()), "edges": list(edges.values()),
                     "thresholds": thresholds, "log": decision_log})
    return {"ok": True, "name": path.stem, "count": len(pins)}

@router.delete("/api/scenarios/{name}")
async def delete_scenario(name: str):
    path = _scenario_path(name)
    if not path.exists():
        raise HTTPException(404)
    path.unlink()
    return {"ok": True}

@router.post("/api/state/clear")
async def clear_state():
    pins.clear(); injects.clear(); edges.clear(); thresholds.clear(); decision_log.clear()
    await broadcast({"type": "full_state", "pins": {}, "injects": [], "edges": [],
                     "thresholds": [], "log": []})
    return {"ok": True}
