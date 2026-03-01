"""
FieldTriage AI — FastAPI application entry-point.

Run locally:
    uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import config

# Lifespan — startup / shutdown hooks
@asynccontextmanager
async def lifespan(app: FastAPI):
    config.CAPTURES_DIR.mkdir(exist_ok=True)
    # Future: initialise DB, start sensor listeners, etc.
    yield
    # Future: cleanup resources


# App factory
app = FastAPI(
    title="FieldTriage AI",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files & templates
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
app.mount(
    "/api/captures",
    StaticFiles(directory=config.CAPTURES_DIR),
    name="captures",
)
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


# Health check
@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "mock_mode": config.MOCK_MODE,
        "vlm_model": config.VLM_MODEL,
    }


# Page routes (served via Jinja2. frontend dev will fill in templates)
@app.get("/")
async def page_triage(request: Request):
    return templates.TemplateResponse("triage.html", {"request": request})


@app.get("/log")
async def page_log(request: Request):
    return templates.TemplateResponse("log.html", {"request": request})


@app.get("/log/{entry_id:int}")
async def page_detail(request: Request, entry_id: int):
    return templates.TemplateResponse("detail.html", {"request": request, "entry_id": entry_id})


# API endpoint placeholders
@app.get("/api/camera/stream")
async def camera_stream():
    return JSONResponse({"detail": "Not implemented — see BE-3"}, status_code=501)


@app.post("/api/capture")
async def capture():
    return JSONResponse({"detail": "Not implemented — see BE-6"}, status_code=501)


@app.post("/api/entries/{entry_id}/chat")
async def entry_chat(entry_id: int):
    return JSONResponse({"detail": "Not implemented — see BE-6"}, status_code=501)


@app.get("/api/temperature")
async def temperature():
    return JSONResponse({"detail": "Not implemented — see BE-4"}, status_code=501)


@app.get("/api/entries")
async def list_entries():
    return JSONResponse({"detail": "Not implemented — see BE-6"}, status_code=501)


@app.get("/api/entries/{entry_id}")
async def get_entry(entry_id: int):
    return JSONResponse({"detail": "Not implemented — see BE-6"}, status_code=501)


@app.post("/api/entries/{entry_id}/escalate")
async def escalate_entry(entry_id: int):
    return JSONResponse({"detail": "Not implemented — see BE-6"}, status_code=501)


@app.post("/api/sync")
async def sync_entries():
    return JSONResponse({"detail": "Not implemented — see STRETCH-A"}, status_code=501)


@app.get("/api/guidance/{entry_id}")
async def get_guidance(entry_id: int):
    return JSONResponse({"detail": "Not implemented — see STRETCH-A"}, status_code=501)
