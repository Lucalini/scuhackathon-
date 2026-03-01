import base64
import logging

import config
import database
from services.camera import capture_snapshot
from services.inference import assess_wound, chat_followup as _vlm_chat
from services.sensors import read_temperature

logger = logging.getLogger(__name__)

_image_cache: dict[int, str] = {}


def should_escalate(
    severity: int, confidence: float, manual: bool = False
) -> tuple[bool, str]:
    if manual:
        return True, "manual"
    if severity >= config.ESCALATION_SEVERITY_THRESHOLD:
        return True, "auto_severity"
    if confidence < config.ESCALATION_CONFIDENCE_THRESHOLD:
        return True, "low_confidence"
    return False, ""


async def perform_triage() -> dict:
    image_b64, filename = await capture_snapshot()

    temp = read_temperature()

    result = await assess_wound(image_b64)
    severity = result["severity"]
    confidence = result["confidence"]
    reasoning = result["reasoning"]

    escalated, escalation_reason = should_escalate(severity, confidence)

    existing = await database.list_entries()
    patient_id = f"Patient #{len(existing) + 1}"

    entry_id = await database.create_entry(
        patient_id=patient_id,
        image_filename=filename,
        temperature_c=temp,
        severity=severity,
        confidence=confidence,
        vlm_reasoning=reasoning,
        escalated=escalated,
        escalation_reason=escalation_reason or None,
    )

    _image_cache[entry_id] = image_b64

    entry = await database.get_entry(entry_id)
    logger.info(
        "Triage complete: id=%d severity=%d confidence=%.1f escalated=%s",
        entry_id,
        severity,
        confidence,
        escalated,
    )
    return entry  # type: ignore[return-value]


async def get_image_base64(entry_id: int, image_filename: str) -> str:
    cached = _image_cache.get(entry_id)
    if cached is not None:
        return cached

    filepath = config.CAPTURES_DIR / image_filename
    raw = await _read_bytes(filepath)
    b64 = base64.b64encode(raw).decode("ascii")
    _image_cache[entry_id] = b64
    return b64


async def followup_chat(entry_id: int, question: str) -> str:
    entry = await database.get_entry(entry_id)
    if entry is None:
        raise ValueError(f"Entry {entry_id} not found")

    image_b64 = await get_image_base64(entry_id, entry["image_filename"])
    history: list[dict] = entry.get("chat_history") or []

    answer = await _vlm_chat(image_b64, question, history)

    history.append({"q": question, "a": answer})
    await database.update_entry(entry_id, chat_history=history)

    logger.info("Follow-up chat entry=%d turns=%d", entry_id, len(history))
    return answer


async def _read_bytes(path) -> bytes:
    """Read a file from disk in a thread so we don't block the event loop."""
    import asyncio
    return await asyncio.to_thread(path.read_bytes)
