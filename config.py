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

# On-device VLM
VLM_MODEL = os.getenv("VLM_MODEL", "qwen3-vl:2b")
VLM_TIMEOUT_S = int(os.getenv("VLM_TIMEOUT_S", "60"))

# Direct Hailo Python bridge
HAILO_MODULE = os.getenv("HAILO_MODULE", "")
HAILO_ASSESS_CALLABLE = os.getenv("HAILO_ASSESS_CALLABLE", "assess_wound")
HAILO_CHAT_CALLABLE = os.getenv("HAILO_CHAT_CALLABLE", "chat_followup")

TRIAGE_PROMPT = (
    "You are a field triage assistant. Assess this wound image.\n\n"

    "Assign severity by checking each level top-down. "
    "Stop at the FIRST level where ANY listed sign is present.\n"
    "Severity levels: 0 = NON-ISSUE, 1 = MINOR, 2 = MODERATE, 3 = SEVERE\n"

    "3 SEVERE — check first:\n"
    "- Exposed fat, muscle, tendon, or bone\n"
    "- Heavy or uncontrolled bleeding\n"
    "- Full-thickness burn (charred, white, or waxy skin)\n"
    "- Visible crush deformity or amputation\n\n"

    "2 MODERATE — check second:\n"
    "- Open wound with gaping or separated edges\n"
    "- Burn with visible blisters\n"
    "- Pus, red streaking from wound, or hot swollen wound margins\n"
    "- Penetrating wound or embedded foreign body\n\n"

    "1 MINOR — check third:\n"
    "- Bruising or discoloration with intact skin\n"
    "- Superficial scrape or abrasion (surface-level skin damage)\n"
    "- Small cut with edges that naturally close\n"
    "- Swelling without deformity or open wound\n\n"

    "0 NON-ISSUE — default if none of the above are visible.\n\n"

    "CONFIDENCE — score 0 to 100:\n"
    "80-100: Wound in focus, well-lit, fully visible, unambiguous type.\n"
    "50-79: Partial view, moderate blur, or borderline between two levels.\n"
    "Below 50: Poor image, wound barely visible, or unclear.\n\n"

    "Respond ONLY in this exact format:\n"
    "SEVERITY: <0|1|2|3>\n"
    "CONFIDENCE: <0-100>\n"
    "REASONING: <One concise sentence on which specific sign(s) you identified and why they match that severity level>"
)

CHAT_SYSTEM_PROMPT = (
    "You are a field medical triage assistant with wound assessment expertise. "
    "You help first responders evaluate injuries from images. "
    "Give practical, actionable guidance. Be direct and concise."
    "Limit your response to a maximum of two sentences. Plain text only."
    "If you are uncertain, say so rather than guessing."
)

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
MOCK_IMAGE_PATH = BASE_DIR / "static" / "mock" / "mockBruise.jpeg"

# Remote server (stretch goal — sync + doctor dashboard)
REMOTE_SERVER_URL = os.getenv("REMOTE_SERVER_URL", "http://localhost:8080")
