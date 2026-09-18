"""Filesystem paths and third-party service configuration."""
import sys
from pathlib import Path
from typing import Dict

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

# Cap returned OSM results to prevent the browser map from freezing when
# querying a dense urban area (e.g. ATMs or telecom masts in a city center).
OSM_RESULT_CAP = 200

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
