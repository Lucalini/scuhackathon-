from __future__ import annotations

import logging

from services.inference_common import InferenceError, parse_vlm_response
import services.inference_hailo as _hailo_backend

logger = logging.getLogger(__name__)


def init_inference() -> None:
    _hailo_backend.init_backend()
    logger.info("Inference backend initialised (hailo)")


async def shutdown_inference() -> None:
    await _hailo_backend.shutdown_backend()
    logger.info("Inference backend shut down (hailo)")


async def assess_wound(image_base64: str) -> dict:
    raw_text = await _hailo_backend.assess_raw(image_base64)
    logger.info("assess_wound ← raw backend response: %s", raw_text[:200])
    return parse_vlm_response(raw_text)


async def chat_followup(image_base64: str, question: str, history: list[dict]) -> str:
    answer = await _hailo_backend.chat_raw(image_base64, question, history)
    logger.info("chat_followup ← answer: %s", answer[:200])
    return answer
