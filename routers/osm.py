"""Outbound lookups: Nominatim geocoding and Overpass infrastructure search.

The only routes that leave the machine.
"""
import httpx
from fastapi import APIRouter, HTTPException

import config
from models import GeoReq, OSMReq

router = APIRouter()

@router.post("/api/geocode")
async def geocode(req: GeoReq):
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": req.query, "format": "json", "limit": 5},
            headers={"User-Agent": "COPPIR/1.0"},
        )
        return r.json()

@router.post("/api/search/osm")
async def search_osm(req: OSMReq):
    tmpl = config.OSM_FILTERS.get(req.category)
    if not tmpl:
        raise HTTPException(400, f"Unknown category: {req.category}")

    radius_m = int(req.radius_mi * 1609.34)
    body = tmpl.format(r=radius_m, lat=req.lat, lon=req.lon)
    # timeout:40 is the server-side Overpass query budget in seconds.
    # out center returns way centroids instead of full geometry, keeping responses small.
    query = f"[out:json][timeout:40];({body});out center qt;"

    last_err = "all mirrors failed"
    async with httpx.AsyncClient(timeout=50, headers={"User-Agent": "COPPIR/1.0"}) as c:
        for mirror in config.OVERPASS_MIRRORS:
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
        if len(results) >= config.OSM_RESULT_CAP:  # see config.OSM_RESULT_CAP
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
