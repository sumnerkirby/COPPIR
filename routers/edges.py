"""Edges: dependencies and links drawn between two pins."""
import uuid

from fastapi import APIRouter, HTTPException

from models import EdgeIn
from state import broadcast, edges, pins

router = APIRouter()

@router.get("/api/edges")
async def get_edges():
    return list(edges.values())

@router.post("/api/edges", status_code=201)
async def create_edge(edge: EdgeIn):
    if edge.from_pid not in pins or edge.to_pid not in pins:
        raise HTTPException(400, "Both pins must exist")
    eid = str(uuid.uuid4())
    edges[eid] = {**edge.model_dump(), "id": eid}
    await broadcast({"type": "edge_add", "edge": edges[eid]})
    return edges[eid]

@router.delete("/api/edges/{eid}")
async def delete_edge(eid: str):
    if eid not in edges:
        raise HTTPException(404)
    del edges[eid]
    await broadcast({"type": "edge_delete", "eid": eid})
    return {"ok": True}
