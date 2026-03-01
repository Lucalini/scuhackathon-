"""
Centralised config
"""

from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
CAPTURES_DIR = BASE_DIR / "captures"
DATABASE_PATH = BASE_DIR / "fieldtriage.db"

# Set MOCK_MODE=0 in the environment on the Pi
# Leave unset on a laptop (defaults True) for mock data
MOCK_MODE: bool = os.getenv("MOCK_MODE", "1") not in ("0", "false", "False")

# FastAPI / Uvicorn
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

# Hailo-Ollama (on-device VLM)
HAILO_OLLAMA_URL = os.getenv("HAILO_OLLAMA_URL", "http://localhost:11434")
VLM_MODEL = os.getenv("VLM_MODEL", "qwen2-vl-2b-instruct")
VLM_TIMEOUT_S = int(os.getenv("VLM_TIMEOUT_S", "60"))

TRIAGE_PROMPT = (
    "You are a field medical triage assistant. Examine this wound image. "
    "Respond ONLY in this exact format:\n"
    "SEVERITY: [0|1|2|3]\n"
    "CONFIDENCE: [0-100]\n"
    "REASONING: [one sentence]\n\n"
    "Where 0=Non-issue, 1=Minor, 2=Moderate, 3=Severe/Urgent."
)

CHAT_SYSTEM_PROMPT = "You are a field medical triage assistant."

# Escalation thresholds
ESCALATION_SEVERITY_THRESHOLD = int(os.getenv("ESCALATION_SEVERITY_THRESHOLD", "3"))
ESCALATION_CONFIDENCE_THRESHOLD = float(os.getenv("ESCALATION_CONFIDENCE_THRESHOLD", "60"))

# GPIO / Sensors
GPIO_BUTTON_PIN = int(os.getenv("GPIO_BUTTON_PIN", "17"))
DS18B20_BASE_DIR = "/sys/bus/w1/devices/"

# Camera
CAMERA_RESOLUTION = (640, 480)
CAMERA_JPEG_QUALITY = 85
CAMERA_STREAM_FPS = int(os.getenv("CAMERA_STREAM_FPS", "24"))
MOCK_IMAGE_PATH = BASE_DIR / "static" / "mock" / "test_wound.jpeg"

# Remote server (stretch goal — sync + doctor dashboard)
REMOTE_SERVER_URL = os.getenv("REMOTE_SERVER_URL", "http://localhost:8080")
