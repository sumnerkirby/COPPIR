from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, List
from contextlib import asynccontextmanager
import sys, json, uuid, httpx, re

# Allowlists for enum-style fields. Validated at the Pydantic layer so invalid
# values are rejected before touching in-memory state or being broadcast to clients.
_VALID_STATUS    = {"Clean", "Monitored", "Contained", "Under Investigation", "Compromised"}
_VALID_OP_STATUS = {"Healthy", "Degraded", "Critical", "Offline"}
_VALID_SEVERITY  = {"info", "warning", "critical"}
_VALID_SECTOR    = {"all", "medical", "government", "power", "emergency", "civilian", "financial"}
_HEX_RE          = re.compile(r'^#[0-9a-fA-F]{6}$')


def _non_blank(v):
    """Trim a name-ish field and reject it if nothing is left.

    min_length alone lets "   " through, which puts a pin on the map with no
    readable label and no way to find it by filtering.
    """
    if v is None:
        return v
    v = v.strip()
    if not v:
        raise ValueError("must not be blank")
    return v

# Cap returned OSM results to prevent the browser map from freezing when
# querying a dense urban area (e.g. ATMs or telecom masts in a city center).
OSM_RESULT_CAP = 200
from datetime import datetime
from pathlib import Path

if getattr(sys, 'frozen', False):
    # PyInstaller bundles static/ into sys._MEIPASS alongside the executable.
    # Scenarios must live outside the bundle because it may be read-only (e.g.
    # inside a macOS .app); place them next to the executable instead.
    STATIC_DIR    = Path(sys._MEIPASS) / 'static'
    SCENARIOS_DIR = Path(sys.executable).parent / 'scenarios'
else:
    STATIC_DIR    = Path(__file__).parent / 'static'
    SCENARIOS_DIR = Path(__file__).parent / 'scenarios'
SCENARIOS_DIR.mkdir(parents=True, exist_ok=True)

# All application state is in-memory. There is no database; the scenario
# save/load endpoints are the only persistence mechanism.
pins: Dict[str, dict] = {}
injects: Dict[str, dict] = {}
edges: Dict[str, dict] = {}
thresholds: List[dict] = []
decision_log: List[dict] = []
clients: set[WebSocket] = set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="COPPIR", lifespan=lifespan)
# CORS is restricted to the local server origin. The app is designed for
# single-machine use, so cross-origin requests from other hosts are not needed.
app.add_middleware(CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000", "http://localhost:8000"],
    allow_methods=["*"], allow_headers=["*"])


async def broadcast(msg: dict):
    dead = set()
    for ws in clients:
        try:
            await ws.send_json(msg)
        except Exception:
            dead.add(ws)
    clients.difference_update(dead)


# ---------- models ----------

class PinIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    category: str = Field("Asset", max_length=100)

    @field_validator("name", "category")
    @classmethod
    def val_non_blank(cls, v):
        return _non_blank(v)
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    status: str = "Clean"
    op_status: str = "Healthy"
    pin_color: Optional[str] = None
    notes: str = Field("", max_length=2000)

    @field_validator("status")
    @classmethod
    def val_status(cls, v):
        if v not in _VALID_STATUS: raise ValueError(f"Invalid status: {v}")
        return v

    @field_validator("op_status")
    @classmethod
    def val_op_status(cls, v):
        if v not in _VALID_OP_STATUS: raise ValueError(f"Invalid op_status: {v}")
        return v

    @field_validator("pin_color")
    @classmethod
    def val_pin_color(cls, v):
        if v is not None and not _HEX_RE.match(v): raise ValueError("pin_color must be #RRGGBB")
        return v

class PinUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    category: Optional[str] = Field(None, max_length=100)

    @field_validator("name", "category")
    @classmethod
    def val_non_blank(cls, v):
        return _non_blank(v)
    status: Optional[str] = None
    op_status: Optional[str] = None
    pin_color: Optional[str] = None
    notes: Optional[str] = Field(None, max_length=2000)

    @field_validator("status")
    @classmethod
    def val_status(cls, v):
        if v is not None and v not in _VALID_STATUS: raise ValueError(f"Invalid status: {v}")
        return v

    @field_validator("op_status")
    @classmethod
    def val_op_status(cls, v):
        if v is not None and v not in _VALID_OP_STATUS: raise ValueError(f"Invalid op_status: {v}")
        return v

    @field_validator("pin_color")
    @classmethod
    def val_pin_color(cls, v):
        if v is not None and not _HEX_RE.match(v): raise ValueError("pin_color must be #RRGGBB")
        return v

class GeoReq(BaseModel):
    query: str = Field(..., min_length=1, max_length=300)

class NewPinData(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    category: str = Field("Asset", max_length=100)

    @field_validator("name", "category")
    @classmethod
    def val_non_blank(cls, v):
        return _non_blank(v)
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    status: str = "Under Investigation"

    @field_validator("status")
    @classmethod
    def val_status(cls, v):
        if v not in _VALID_STATUS: raise ValueError(f"Invalid status: {v}")
        return v

class InjectIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., max_length=2000)
    severity: str = "warning"
    target_pid: Optional[str] = None
    target_status: Optional[str] = None
    new_pin: Optional[NewPinData] = None

    @field_validator("severity")
    @classmethod
    def val_severity(cls, v):
        if v not in _VALID_SEVERITY: raise ValueError(f"Invalid severity: {v}")
        return v

    @field_validator("target_status")
    @classmethod
    def val_target_status(cls, v):
        if v is not None and v not in _VALID_STATUS: raise ValueError(f"Invalid target_status: {v}")
        return v

class LogEntry(BaseModel):
    action: str = Field(..., min_length=1, max_length=500)
    asset_name: Optional[str] = Field(None, max_length=200)
    asset_pid: Optional[str] = None
    notes: str = Field("", max_length=2000)

class ScenarioReq(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)

class BulkStatusReq(BaseModel):
    status: Optional[str] = None
    op_status: Optional[str] = None
    category: Optional[str] = Field(None, max_length=100)

    @field_validator("status")
    @classmethod
    def val_status(cls, v):
        if v is not None and v not in _VALID_STATUS: raise ValueError(f"Invalid status: {v}")
        return v

    @field_validator("op_status")
    @classmethod
    def val_op_status(cls, v):
        if v is not None and v not in _VALID_OP_STATUS: raise ValueError(f"Invalid op_status: {v}")
        return v

class BulkPinItem(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    category: str = Field("Asset", max_length=100)

    @field_validator("name", "category")
    @classmethod
    def val_non_blank(cls, v):
        return _non_blank(v)
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)

class BulkCreate(BaseModel):
    items: List[BulkPinItem] = Field(default_factory=list)
    status: str = "Clean"
    op_status: str = "Healthy"
    pin_color: Optional[str] = None

    @field_validator("status")
    @classmethod
    def val_status(cls, v):
        if v not in _VALID_STATUS: raise ValueError(f"Invalid status: {v}")
        return v

    @field_validator("op_status")
    @classmethod
    def val_op_status(cls, v):
        if v not in _VALID_OP_STATUS: raise ValueError(f"Invalid op_status: {v}")
        return v

    @field_validator("pin_color")
    @classmethod
    def val_pin_color(cls, v):
        if v is not None and not _HEX_RE.match(v): raise ValueError("pin_color must be #RRGGBB")
        return v

class EdgeIn(BaseModel):
    from_pid: str
    to_pid: str
    label: str = Field("", max_length=200)
    edge_type: str = "connection"

class ThresholdIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    sector: str
    below_pct: int = Field(50, ge=0, le=100)
    severity: str = "warning"

    @field_validator("sector")
    @classmethod
    def val_sector(cls, v):
        if v not in _VALID_SECTOR: raise ValueError(f"Invalid sector: {v}")
        return v

    @field_validator("severity")
    @classmethod
    def val_severity(cls, v):
        if v not in _VALID_SEVERITY: raise ValueError(f"Invalid severity: {v}")
        return v

class OSMReq(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    radius_mi: float = Field(15.0, gt=0, le=100)
    category: str



# ---------- Overpass config ----------

# Multiple mirrors because the primary Overpass API is rate-limited and
# occasionally unavailable. The list is tried in order; 429 (rate limit) and
# 504 (gateway timeout) both trigger a fallthrough to the next mirror.
OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.fr/api/interpreter",
]

def _tags(*pairs: tuple) -> str:
    """Build node+way clauses for multiple tag pairs, to be .format()'d later."""
    out = []
    for key, val in pairs:
        filt = f'["{key}"="{val}"](around:{{r}},{{lat}},{{lon}})'
        out.append(f"node{filt}; way{filt};")
    return " ".join(out)

OSM_FILTERS: Dict[str, str] = {
    "Hospitals": _tags(
        ("amenity", "hospital"),
        ("healthcare", "hospital"),
        ("amenity", "clinic"),
        ("healthcare", "clinic"),
    ),
    "Government Buildings": _tags(
        ("amenity", "townhall"),
        ("amenity", "courthouse"),
        ("building", "government"),
        ("office", "government"),
        ("amenity", "government"),
    ),
    "Power Plants": _tags(
        ("power", "plant"),
        ("power", "substation"),
        ("power", "generator"),
    ),
    "Fire Stations": _tags(
        ("amenity", "fire_station"),
    ),
    "Police Stations": _tags(
        ("amenity", "police"),
    ),
    "Data Centers": _tags(
        ("building", "data_center"),
        ("telecom", "data_center"),
        ("facility", "data_center"),
    ),
    "Universities": _tags(
        ("amenity", "university"),
        ("amenity", "college"),
    ),
    "Banks": _tags(
        ("amenity", "bank"),
        ("amenity", "atm"),
    ),
    "Water Systems": _tags(
        ("man_made", "water_tower"),
        ("amenity", "water_works"),
        ("man_made", "water_works"),
        ("amenity", "water_point"),
        ("utility", "water"),
    ),
    "Transportation Hubs": _tags(
        ("aeroway", "aerodrome"),
        ("railway", "station"),
        ("amenity", "bus_station"),
        ("public_transport", "station"),
        ("amenity", "ferry_terminal"),
    ),
    "Telecom Infrastructure": _tags(
        ("man_made", "mast"),
        ("man_made", "tower"),
        ("communication", "mobile_phone"),
        ("telecom", "exchange"),
        ("building", "telecommunications"),
    ),
}


# ---------- routes ----------

@app.get("/")
async def root():
    return FileResponse(STATIC_DIR / "index.html")

@app.get("/api/pins")
async def get_pins():
    return pins

@app.post("/api/pins", status_code=201)
async def create_pin(pin: PinIn):
    pid = str(uuid.uuid4())
    now = datetime.now().isoformat()
    pins[pid] = {**pin.model_dump(), "id": pid, "pinned_at": now,
                 "status_history": [{"status": pin.status, "timestamp": now}]}
    await broadcast({"type": "pin_add", "pin": pins[pid]})
    return pins[pid]

@app.post("/api/pins/bulk", status_code=201)
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

@app.put("/api/pins/{pid}")
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

@app.delete("/api/pins/{pid}")
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

@app.post("/api/geocode")
async def geocode(req: GeoReq):
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": req.query, "format": "json", "limit": 5},
            headers={"User-Agent": "COPPIR/1.0"},
        )
        return r.json()

@app.post("/api/search/osm")
async def search_osm(req: OSMReq):
    tmpl = OSM_FILTERS.get(req.category)
    if not tmpl:
        raise HTTPException(400, f"Unknown category: {req.category}")

    radius_m = int(req.radius_mi * 1609.34)
    body = tmpl.format(r=radius_m, lat=req.lat, lon=req.lon)
    # timeout:40 is the server-side Overpass query budget in seconds.
    # out center returns way centroids instead of full geometry, keeping responses small.
    query = f"[out:json][timeout:40];({body});out center qt;"

    last_err = "all mirrors failed"
    async with httpx.AsyncClient(timeout=50, headers={"User-Agent": "COPPIR/1.0"}) as c:
        for mirror in OVERPASS_MIRRORS:
            try:
                r = await c.get(mirror, params={"data": query})
                if r.status_code in (429, 504):   # rate-limited or gateway timeout
                    last_err = f"mirror {mirror} returned {r.status_code}"
                    continue
                r.raise_for_status()
                data = r.json()
                break
            except (httpx.RequestError, ValueError) as e:
                last_err = str(e)
                continue
        else:
            raise HTTPException(502, f"Overpass unavailable: {last_err}")

    seen, results = set(), []
    for el in data.get("elements", []):
        if len(results) >= OSM_RESULT_CAP:  # see OSM_RESULT_CAP above
            break
        tags = el.get("tags", {})
        name = (tags.get("name") or tags.get("operator")
                or tags.get("brand") or f"Unnamed {req.category}")
        lat = el.get("lat") or el.get("center", {}).get("lat")
        lon = el.get("lon") or el.get("center", {}).get("lon")
        if lat and lon:
            key = f"{round(lat,5)},{round(lon,5)}"  # deduplicate node+way for same location
            if key not in seen:
                seen.add(key)
                results.append({"name": name, "lat": lat, "lon": lon, "category": req.category})
    return results

@app.get("/api/injects")
async def get_injects():
    return list(injects.values())

@app.post("/api/injects", status_code=201)
async def create_inject(inj: InjectIn):
    iid = str(uuid.uuid4())
    injects[iid] = {**inj.model_dump(), "id": iid,
                    "created_at": datetime.now().isoformat(), "triggered_at": None}
    await broadcast({"type": "inject_queued", "inject": injects[iid]})
    return injects[iid]

@app.delete("/api/injects/{iid}")
async def delete_inject(iid: str):
    if iid not in injects:
        raise HTTPException(404)
    del injects[iid]
    await broadcast({"type": "inject_delete", "iid": iid})
    return {"ok": True}

@app.post("/api/injects/{iid}/trigger")
async def trigger_inject(iid: str):
    if iid not in injects:
        raise HTTPException(404)
    inj = injects[iid]
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

@app.get("/api/log")
async def get_log():
    return decision_log

@app.post("/api/log", status_code=201)
async def add_log(entry: LogEntry):
    rec = {**entry.model_dump(), "id": str(uuid.uuid4()),
           "timestamp": datetime.now().isoformat(), "auto": False}
    decision_log.append(rec)
    await broadcast({"type": "log_entry", "entry": rec})
    return rec

# ---------- scenario management ----------

def _state_payload() -> dict:
    return {"pins": pins, "injects": injects, "edges": edges,
            "thresholds": thresholds, "decision_log": decision_log,
            "saved_at": datetime.now().isoformat()}

def _safe_name(name: str) -> str:
    # Strip anything outside alphanumerics, hyphens, underscores, and spaces
    # so the result is safe as a filesystem filename on all platforms.
    return re.sub(r"[^a-zA-Z0-9_\- ]", "", name).strip()[:64]

@app.get("/api/scenarios")
async def list_scenarios():
    return sorted(f.stem for f in SCENARIOS_DIR.glob("*.json"))

def _scenario_path(name: str) -> Path:
    safe = _safe_name(name)
    if not safe:
        raise HTTPException(400, "Invalid scenario name")
    # Resolve symlinks and ".." components, then confirm the result still sits
    # inside SCENARIOS_DIR. This prevents path traversal via crafted names.
    path = (SCENARIOS_DIR / f"{safe}.json").resolve()
    if not str(path).startswith(str(SCENARIOS_DIR.resolve())):
        raise HTTPException(400, "Invalid scenario name")
    return path

@app.post("/api/scenarios/save")
async def save_scenario(req: ScenarioReq):
    path = _scenario_path(req.name)
    name = path.stem
    path.write_text(json.dumps({**_state_payload(), "name": name}, indent=2))
    return {"ok": True, "name": name}

@app.post("/api/scenarios/load")
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

@app.delete("/api/scenarios/{name}")
async def delete_scenario(name: str):
    path = _scenario_path(name)
    if not path.exists():
        raise HTTPException(404)
    path.unlink()
    return {"ok": True}

@app.delete("/api/pins")
async def clear_pins():
    pids = list(pins.keys())
    pins.clear()
    edges.clear()
    await broadcast({"type": "pins_cleared", "pids": pids})
    return {"ok": True, "count": len(pids)}

@app.post("/api/pins/bulk-status")
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

@app.post("/api/state/clear")
async def clear_state():
    pins.clear(); injects.clear(); edges.clear(); thresholds.clear(); decision_log.clear()
    await broadcast({"type": "full_state", "pins": {}, "injects": [], "edges": [],
                     "thresholds": [], "log": []})
    return {"ok": True}


@app.websocket("/ws")
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


# ---------- edges ----------

@app.get("/api/edges")
async def get_edges():
    return list(edges.values())

@app.post("/api/edges", status_code=201)
async def create_edge(edge: EdgeIn):
    if edge.from_pid not in pins or edge.to_pid not in pins:
        raise HTTPException(400, "Both pins must exist")
    eid = str(uuid.uuid4())
    edges[eid] = {**edge.model_dump(), "id": eid}
    await broadcast({"type": "edge_add", "edge": edges[eid]})
    return edges[eid]

@app.delete("/api/edges/{eid}")
async def delete_edge(eid: str):
    if eid not in edges:
        raise HTTPException(404)
    del edges[eid]
    await broadcast({"type": "edge_delete", "eid": eid})
    return {"ok": True}

# ---------- thresholds ----------

@app.get("/api/thresholds")
async def get_thresholds():
    return thresholds

@app.post("/api/thresholds", status_code=201)
async def create_threshold(t: ThresholdIn):
    rec = {**t.model_dump(), "id": str(uuid.uuid4())}
    thresholds.append(rec)
    return rec

@app.delete("/api/thresholds/{tid}")
async def delete_threshold(tid: str):
    for i, t in enumerate(thresholds):
        if t["id"] == tid:
            thresholds.pop(i)
            return {"ok": True}
    raise HTTPException(404)

# mount static LAST so API routes take priority
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
