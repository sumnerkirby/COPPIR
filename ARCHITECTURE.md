# COPPIR Architecture

## Overview

COPPIR is a single-machine desktop application. There is no cloud component, no external database, and no account system. All state lives in memory for the duration of a session and is persisted only when a user explicitly saves a scenario.

The application has two layers that communicate over localhost:

```
┌─────────────────────────────────────────┐
│  Desktop shell (pywebview)              │
│  Renders a native OS window containing  │
│  a WebKit/WebView2 browser panel        │
│                                         │
│  ┌───────────────────────────────────┐  │
│  │  Frontend  (HTML / CSS / JS)      │  │
│  │  Leaflet map, SITREP strip,       │  │
│  │  toolbars, modals                 │  │
│  └──────────────┬────────────────────┘  │
│                 │  HTTP + WebSocket      │
│                 │  localhost:8000        │
│  ┌──────────────▼────────────────────┐  │
│  │  Backend  (FastAPI / uvicorn)     │  │
│  │  REST API, WebSocket broadcast,   │  │
│  │  OSM queries, scenario I/O        │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

---

## Process Model

### Development (`run.py`)

`run.py` is the entry point for development use. It:

1. Imports `pywebview` immediately so the native window can open before the server is ready.
2. Shows an inline loading screen in the window.
3. Spawns `uvicorn main:app` as a subprocess (`subprocess.Popen`).
4. Polls `http://localhost:8000/` until the server responds.
5. Calls `window.load_url()` to navigate the embedded browser to the app.

### Frozen build (`run.py` frozen branch)

When packaged by PyInstaller, `sys.executable` points to the bundle itself rather than a Python interpreter, so the subprocess approach cannot work. In that case `run.py` detects `sys.frozen` and instead starts uvicorn in a daemon thread within the same process. The rest of the startup sequence (poll → load URL) is identical.

---

## Backend (`main.py`)

**Runtime:** uvicorn (ASGI), FastAPI framework, Python 3.10+

### State

All application state is held in module-level dictionaries and lists. There is no ORM or database.

| Variable | Type | Contents |
|---|---|---|
| `pins` | `Dict[str, dict]` | All placed map pins, keyed by UUID |
| `injects` | `Dict[str, dict]` | Scenario injects (queued events), keyed by UUID |
| `edges` | `Dict[str, dict]` | Connections between pins, keyed by UUID |
| `thresholds` | `List[dict]` | Alert threshold rules |
| `decision_log` | `List[dict]` | Ordered log of all actions |
| `clients` | `set[WebSocket]` | Active WebSocket connections |

Each pin stores a `status_history` list so the edit modal can show a timeline of status changes. The history is appended only when the status actually changes, not on every update.

### API surface

All routes are prefixed with `/api/`. The static file mount (`/`) is registered last so API routes always take priority.

**Pins**

| Method | Path | Description |
|---|---|---|
| GET | `/api/pins` | Return all pins |
| POST | `/api/pins` | Create a single pin |
| POST | `/api/pins/bulk` | Create multiple pins (OSM import) |
| PUT | `/api/pins/{pid}` | Update a pin's fields |
| DELETE | `/api/pins/{pid}` | Delete a pin |
| DELETE | `/api/pins` | Delete all pins |
| POST | `/api/pins/bulk-status` | Set status/op-status on a category |

**Edges**

| Method | Path | Description |
|---|---|---|
| GET | `/api/edges` | Return all edges |
| POST | `/api/edges` | Create an edge between two pins |
| DELETE | `/api/edges/{eid}` | Delete an edge |

**Injects**

| Method | Path | Description |
|---|---|---|
| GET | `/api/injects` | Return all injects |
| POST | `/api/injects` | Queue a new inject |
| DELETE | `/api/injects/{iid}` | Delete an inject |
| POST | `/api/injects/{iid}/trigger` | Fire an inject |

Triggering an inject can atomically: change a target pin's status, create a new pin, and append a log entry — all in one broadcast.

**Log**

| Method | Path | Description |
|---|---|---|
| GET | `/api/log` | Return decision log |
| POST | `/api/log` | Append a manual log entry |

**Scenarios**

| Method | Path | Description |
|---|---|---|
| GET | `/api/scenarios` | List saved scenario names |
| POST | `/api/scenarios/save` | Serialize current state to JSON |
| POST | `/api/scenarios/load` | Replace state from a saved JSON |
| DELETE | `/api/scenarios/{name}` | Delete a saved scenario |
| POST | `/api/state/clear` | Reset all state to empty |

Scenario files are written to a `scenarios/` directory next to the executable. Filenames are sanitized to alphanumerics, hyphens, underscores, and spaces, and the resolved path is checked against `scenarios/` to prevent path traversal.

**Geocoding / OSM**

| Method | Path | Description |
|---|---|---|
| POST | `/api/geocode` | Forward a query to Nominatim |
| POST | `/api/search/osm` | Query Overpass for infrastructure by category and radius |

The OSM search tries three public Overpass mirrors in sequence, falling through on HTTP 429 (rate limit) or 504 (gateway timeout). Results are capped at 200 after deduplication by rounded coordinate.

**Thresholds**

| Method | Path | Description |
|---|---|---|
| GET | `/api/thresholds` | Return all thresholds |
| POST | `/api/thresholds` | Create a threshold rule |
| DELETE | `/api/thresholds/{tid}` | Delete a threshold rule |

**WebSocket**

`GET /ws` — on connect, the server immediately sends a `full_state` message containing all current pins, edges, injects, thresholds, and log entries so the new client is synchronized. All subsequent state changes are broadcast to every connected client as typed JSON messages.

WebSocket message types:

| Type | Trigger |
|---|---|
| `full_state` | On connect, scenario load, or state clear |
| `pin_add` | Single pin created |
| `bulk_add` | Batch of pins created |
| `pin_update` | Pin fields changed |
| `pin_delete` | Pin removed |
| `pins_cleared` | All pins deleted |
| `bulk_update` | Bulk status change applied |
| `edge_add` | Edge created |
| `edge_delete` | Edge removed |
| `inject_queued` | Inject created |
| `inject_delete` | Inject deleted |
| `inject_triggered` | Inject fired (carries updated pins + log entry) |
| `log_entry` | Manual log entry added |

### Input validation

All request bodies are Pydantic v2 models. String fields have `min_length` / `max_length` constraints. Enum-style fields (`status`, `op_status`, `severity`, `sector`) are validated against explicit allowlists. Color fields are validated against `^#[0-9a-fA-F]{6}$`. Invalid requests return HTTP 422 before touching any state.

---

## Frontend (`static/`)

**Runtime:** plain ES2020 JavaScript, no build step or bundler.

| File | Role |
|---|---|
| `index.html` | Shell: loading screen, SITREP strip, toolbar, map container, all modals |
| `app.js` | All application logic (~1900 lines) |
| `style.css` | All styles — terminal green-on-black theme |

### Map

Leaflet.js with Esri Dark Gray Canvas tiles, in two layers: terrain and labels. The service is only cached to zoom 16, so both layers set `maxNativeZoom: 16` with `maxZoom: 19` and let Leaflet upscale past that. This replaced CartoDB, which now requires an API key and watermarks unauthenticated tiles while still returning HTTP 200. The map is initialized to a US-centered view. Pins are `L.marker` instances with custom `L.divIcon` HTML that encodes security status (fill color) and operational status (border color and style). The icon HTML is constructed from validated server data only; all user-supplied strings are passed through `escHtml()` before insertion.

Edges are `L.polyline` instances drawn between pin coordinates. They are redrawn whenever either endpoint pin is updated.

### SITREP strip

The strip at the top of the screen is updated by `updateSitrep()`, which is debounced at 80ms so bulk imports (50+ pins) do not trigger 50 full recalculations. It shows:

- Raw counts per security status and operational status
- One SVG arc wheel per sector (medical, government, power, emergency, civilian, financial), where the arc percentage is the mean `STATUS_SCORE` of all pins in that sector's categories
- Custom metric wheels (percentage values stored in `localStorage`)

The `WHEEL_C` constant (`2 * Math.PI * 19`) is the circumference of the SVG circles used for all wheels; 19 matches the `r` attribute in the SVG markup.

### WebSocket client

`connectWS()` opens a WebSocket to `/ws`. On disconnect, it retries with exponential backoff starting at 1 second, doubling each attempt, capped at 30 seconds. The backoff resets to 1 second on a successful reconnect. A small status dot in the brand area turns red while disconnected.

### Real-time dispatch

`ws.onmessage` receives all server-pushed events and dispatches them by `msg.type`. `updateSitrep()` and `refreshBulkCategories()` are called after every message. Heat layers are torn down and rebuilt if active, so they stay current.

### Security helpers

Two module-level functions guard all dynamic HTML construction:

- `escHtml(s)` — encodes `& < > " '` before inserting user-supplied text into `innerHTML`
- `safeColor(c)` — validates `#RRGGBB` format before using a color in a CSS `style` attribute; returns `#888888` on failure

All `onclick` attribute strings built with user data use `JSON.stringify()` rather than string concatenation to prevent JS injection.

---

## Packaging (`packaging/`)

PyInstaller is used to produce self-contained distributable builds. The spec file (`coppir.spec`) targets `--onedir` mode, which produces a folder containing the executable and its dependencies rather than a single file. This is more compatible with pywebview's platform backends (WebKit on macOS, WebView2 on Windows, WebKit2GTK on Linux), which are OS-level shared libraries.

Key bundling decisions:

- `static/` is included as a data directory mapped to `static/` inside `sys._MEIPASS`.
- `scenarios/` is intentionally excluded from the bundle and written to a writable location beside the executable at runtime.
- Uvicorn's protocol and loop backends are listed as `hiddenimports` because uvicorn loads them by string name at runtime, which PyInstaller's static analysis cannot follow.
- The macOS build produces a `.app` bundle wrapped in a `.dmg`. Windows produces a `.zip`. Linux produces a `.tar.gz` plus a `.desktop` launcher file.
- Linux builds link against the system WebKit2GTK library, which cannot be bundled and must be installed separately on the end-user machine.

Icon generation (`make_icons.py`) uses Pillow to render the eye icon from geometry (quadratic Bezier arcs) at 4x resolution and downsamples with LANCZOS for clean anti-aliasing at all sizes.
