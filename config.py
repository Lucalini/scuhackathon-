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

TRIAGE_PROMPT = """You are a field triage expert specialized in assessing wounds from smartphone photos for rapid severity classification.

Analyze ONLY the visual evidence in the image:
- Wound size (estimate relative to known objects if no scale)
- Depth indicators (shadows, exposed layers, tissue visibility)
- Bleeding (none, oozing, flowing, spurting)
- Tissue appearance (color, edges, necrosis, exposed fat/muscle/bone)
- Surrounding signs (swelling, redness extent, pus, streaking, bruising)
- Overall clarity (focus, lighting, obstructions)

Severity levels (use ONLY these definitions):
0 = NON-ISSUE: No open wound OR only intact-skin abrasion/bruise/scratch with no skin break.
1 = MINOR: Superficial (epidermis only), small (<2 cm), minimal or no bleeding, clean edges, no or minimal surrounding redness/swelling.
2 = MODERATE: Partial-thickness (into dermis), 2–5 cm or multiple small wounds, moderate controllable bleeding, mild-moderate swelling/redness, possible minor contamination.
3 = SEVERE: Full-thickness or deeper (subcutaneous fat, muscle, tendon, bone visible), >5 cm or penetrating, heavy/uncontrolled bleeding, necrosis, pus, red streaking, or located on face/hands/joints/genitals.

CONFIDENCE (0–100):
- 80–100: Wound fully in focus, well-lit, unambiguous features, clear depth/bleeding cues.
- 50–79: Moderate blur, partial view, borderline between two levels, or missing scale.
- <50: Poor lighting/focus, wound barely visible, heavy obstruction, or no clear wound.

Respond ONLY with a single valid JSON object. No explanations, no extra text, no markdown.
{
  "severity": <integer 0-3>,
  "confidence": <integer 0-100>,
  "reasoning": "<ONE concise sentence naming the key visual signs and why they map to that exact severity level>"
}"""

FEW_SHOT_EXAMPLES: list[dict[str, str]] = [
    {
        "image_path": str(BASE_DIR / "static" / "mock" / "mockBruise.jpeg"),
        "response": '{"severity": 0, "confidence": 90, "reasoning": "Large bruise on knee with intact skin and no open wound, skin break, or swelling, consistent with a non-issue."}',
    },
    {
        "image_path": str(BASE_DIR / "static" / "mock" / "SeconDegreeBurn.png"),
        "response": '{"severity": 3, "confidence": 88, "reasoning": "Extensive second-degree burn covering a large area of the upper back with raw exposed dermis, blistering, and multiple affected zones far exceeding 5 cm, indicating severe severity."}',
    },
    {
        "image_path": str(BASE_DIR / "static" / "mock" / "mockBurn.jpeg"),
        "response": '{"severity": 3, "confidence": 93, "reasoning": "Full-thickness wound on the heel with exposed subcutaneous tissue, necrotic discoloration, and surrounding erythema indicating severe injury requiring immediate care."}',
    },
    {
        "image_path": str(BASE_DIR / "static" / "mock" / "SevereExample.png"),
        "response": '{"severity": 3, "confidence": 95, "reasoning": "Deep forearm laceration with widely separated edges, exposed muscle tissue, and heavy active bleeding indicating severe full-thickness injury."}',
    },
]

CHAT_SYSTEM_PROMPT = (
    "You are a field medical triage expert with wound assessment expertise. "
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
CAMERA_RESOLUTION = (
    int(os.getenv("CAMERA_WIDTH", "1080")),
    int(os.getenv("CAMERA_HEIGHT", "1920")),
)
CAMERA_JPEG_QUALITY = int(os.getenv("CAMERA_JPEG_QUALITY", "92"))
CAMERA_STREAM_FPS = int(os.getenv("CAMERA_STREAM_FPS", "20"))
CAMERA_ENABLE_AWB = os.getenv("CAMERA_ENABLE_AWB", "1") not in ("0", "false", "False")
CAMERA_ENABLE_AE = os.getenv("CAMERA_ENABLE_AE", "1") not in ("0", "false", "False")
CAMERA_COLOR_ORDER = os.getenv("CAMERA_COLOR_ORDER", "grb").strip().lower()
MOCK_IMAGE_PATH = BASE_DIR / "static" / "mock" / "mockBruise.jpeg"

# Remote server (stretch goal — sync + doctor dashboard)
REMOTE_SERVER_URL = os.getenv("REMOTE_SERVER_URL", "http://localhost:8080")
