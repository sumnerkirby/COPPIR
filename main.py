"""COPPIR: the ASGI application.

This module assembles the app and nothing else. State lives in state.py,
request validation in models.py, paths and third-party endpoints in config.py,
and the routes themselves under routers/.

run.py is the entry point; PyInstaller builds from it and imports `app` here.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import config
from routers import edges, injects, log, osm, pins, scenarios, thresholds, ws


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="COPPIR", lifespan=lifespan)
# CORS is restricted to the local server origin. The app is designed for
# single-machine use, so cross-origin requests from other hosts are not needed.
app.add_middleware(CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000", "http://localhost:8000"],
    allow_methods=["*"], allow_headers=["*"])


@app.get("/")
async def root():
    return FileResponse(config.STATIC_DIR / "index.html")


for module in (pins, edges, injects, log, scenarios, thresholds, osm, ws):
    app.include_router(module.router)

# mount static LAST so API routes take priority
app.mount("/", StaticFiles(directory=str(config.STATIC_DIR), html=True), name="static")
