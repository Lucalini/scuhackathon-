"""
FieldTriage AI — FastAPI application entry-point.

Run locally:
    uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

import config
import database
from database import init_db
from services.camera import init_camera, shutdown_camera, mjpeg_stream
from services.inference import InferenceError, init_inference, shutdown_inference
from services.sensors import (
    init_sensors,
    shutdown_sensors,
    read_temperature,
    was_button_pressed,
    simulate_button_press,
)
from services.triage import followup_chat, perform_triage

# Lifespan — startup / shutdown hooks
@asynccontextmanager
async def lifespan(app: FastAPI):
    config.CAPTURES_DIR.mkdir(exist_ok=True)
    await init_db()
    init_camera()
    init_sensors()
    init_inference()
    yield
    await shutdown_inference()
    shutdown_sensors()
    shutdown_camera()


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


def _relative_time(iso_str: str | None) -> str:
    if not iso_str:
        return "—"
    try:
        d = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        delta = (now - d).total_seconds()
        if delta < 60:
            return "Just now"
        if delta < 3600:
            return f"{int(delta // 60)} min ago"
        if delta < 86400:
            return f"{int(delta // 3600)} h ago"
        return d.strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return "—"


def _severity_label(severity: int | None) -> str:
    if severity is None:
        return "—"
    labels = ["NON-ISSUE", "MINOR", "MODERATE", "SEVERE"]
    return labels[severity] if 0 <= severity < len(labels) else "—"


templates.env.filters["relative_time"] = _relative_time
templates.env.filters["severity_label"] = _severity_label


# Health check
@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "mock_mode": config.MOCK_MODE,
        "inference_backend": "hailo",
        "vlm_model": config.VLM_MODEL,
    }


# Page routes (served via Jinja2)
@app.get("/")
async def page_triage(request: Request):
    return templates.TemplateResponse("triage.html", {"request": request})


@app.get("/log")
async def page_log(request: Request):
    entries = await database.list_entries()
    return templates.TemplateResponse("log.html", {"request": request, "entries": entries})


@app.get("/log/{entry_id:int}")
async def page_detail(request: Request, entry_id: int):
    entry = await database.get_entry(entry_id)
    if entry is None:
        return JSONResponse({"detail": "Entry not found"}, status_code=404)
    return templates.TemplateResponse("detail.html", {"request": request, "entry": entry})


@app.get("/classic")
async def page_classic():
    """Redirect to triage (same page, classic layout)."""
    return RedirectResponse(url="/", status_code=302)


@app.get("/api/camera/stream")
async def camera_stream():
    return StreamingResponse(
        mjpeg_stream(),
        media_type="multipart/x-mixed-replace; boundary=FRAME",
    )


@app.post("/api/capture")
async def capture():
    """Snapshot → VLM assess → escalation check → DB save."""
    try:
        entry = await perform_triage()
    except InferenceError as exc:
        return JSONResponse(
            {"detail": f"VLM inference failed: {exc}"},
            status_code=502,
        )
    return entry


class _ChatRequest(BaseModel):
    question: str


@app.post("/api/entries/{entry_id}/chat")
async def entry_chat(entry_id: int, body: _ChatRequest):
    try:
        answer = await followup_chat(entry_id, body.question)
    except ValueError:
        return JSONResponse({"detail": "Entry not found"}, status_code=404)
    except InferenceError as exc:
        return JSONResponse(
            {"detail": f"VLM inference failed: {exc}"},
            status_code=502,
        )
    return {"answer": answer}


@app.get("/api/temperature")
async def temperature():
    from datetime import datetime, timezone

    temp = read_temperature()
    return {
        "temperature_c": temp,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/api/debug/button-press")
async def debug_button_press():
    simulate_button_press()
    return {"detail": "Button press simulated"}


@app.get("/api/debug/button-status")
async def debug_button_status():
    return {"was_pressed": was_button_pressed()}


@app.get("/api/entries")
async def api_list_entries():
    entries = await database.list_entries()
    return JSONResponse(content=entries)


@app.get("/api/entries/{entry_id}")
async def api_get_entry(entry_id: int):
    entry = await database.get_entry(entry_id)
    if entry is None:
        return JSONResponse({"detail": "Entry not found"}, status_code=404)
    return entry


@app.post("/api/entries/{entry_id}/escalate")
async def escalate_entry(entry_id: int):
    entry = await database.get_entry(entry_id)
    if entry is None:
        return JSONResponse({"detail": "Entry not found"}, status_code=404)
    await database.update_entry(
        entry_id, escalated=True, escalation_reason="manual"
    )
    updated = await database.get_entry(entry_id)
    return updated


# Stretch-goal stubs (sync + guidance)
@app.post("/api/sync")
async def sync_entries():
    return JSONResponse({"detail": "Not implemented — see STRETCH-A"}, status_code=501)


@app.get("/api/guidance/{entry_id}")
async def get_guidance(entry_id: int):
    return JSONResponse({"detail": "Not implemented — see STRETCH-A"}, status_code=501)
