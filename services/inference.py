from __future__ import annotations

import logging
import re

import httpx

import config

logger = logging.getLogger(__name__)

_client: httpx.AsyncClient | None = None


def init_inference() -> None:
    global _client  # noqa: PLW0603
    if _client is not None:
        return
    _client = httpx.AsyncClient(
        base_url=config.HAILO_OLLAMA_URL,
        timeout=httpx.Timeout(config.VLM_TIMEOUT_S, connect=10.0),
    )
    logger.info(
        "Inference client initialised (base_url=%s, timeout=%ss)",
        config.HAILO_OLLAMA_URL,
        config.VLM_TIMEOUT_S,
    )


async def shutdown_inference() -> None:
    global _client  # noqa: PLW0603
    if _client is not None:
        await _client.aclose()
        _client = None
        logger.info("Inference client shut down")


def _get_client() -> httpx.AsyncClient:
    if _client is None:
        raise RuntimeError("Inference client not initialised — call init_inference() at startup")
    return _client


_RE_SEVERITY = re.compile(r"SEVERITY:\s*(\d)", re.IGNORECASE)
_RE_CONFIDENCE = re.compile(r"CONFIDENCE:\s*(\d+)", re.IGNORECASE)
_RE_REASONING = re.compile(r"REASONING:\s*(.+)", re.IGNORECASE | re.DOTALL)


def parse_vlm_response(text: str) -> dict:
    """
    Expected format:
        SEVERITY: <0-3>
        CONFIDENCE: <0-100>
        REASONING: <text>
    """
    m_sev = _RE_SEVERITY.search(text)
    m_conf = _RE_CONFIDENCE.search(text)
    m_reason = _RE_REASONING.search(text)

    missing = []
    if not m_sev:
        missing.append("SEVERITY")
    if not m_conf:
        missing.append("CONFIDENCE")
    if not m_reason:
        missing.append("REASONING")

    if missing:
        raise InferenceError(
            f"VLM returned unexpected format — missing: {', '.join(missing)}. "
            f"Raw output: {text[:200]}"
        )

    return {
        "severity": max(0, min(3, int(m_sev.group(1)))),
        "confidence": max(0.0, min(100.0, float(m_conf.group(1)))),
        "reasoning": m_reason.group(1).strip(),
    }


class InferenceError(Exception):
    """Raised when the Hailo-Ollama inference call fails."""


# Public API

async def assess_wound(image_base64: str) -> dict:
    client = _get_client()
    payload = {
        "model": config.VLM_MODEL,
        "prompt": config.TRIAGE_PROMPT,
        "images": [image_base64],
        "stream": False,
    }

    logger.info("assess_wound → POST /api/generate (model=%s, image=%d chars)", config.VLM_MODEL, len(image_base64))

    try:
        resp = await client.post("/api/generate", json=payload)
        resp.raise_for_status()
    except httpx.TimeoutException:
        logger.error("assess_wound timed out after %ds", config.VLM_TIMEOUT_S)
        raise InferenceError(f"Wound assessment timed out after {config.VLM_TIMEOUT_S}s")
    except httpx.HTTPError as exc:
        logger.error("assess_wound HTTP error: %s", exc)
        raise InferenceError(f"Wound assessment failed: {exc}") from exc

    body = resp.json()
    raw_text = body.get("response", "")
    logger.info("assess_wound ← raw VLM response: %s", raw_text)

    return parse_vlm_response(raw_text)


async def chat_followup(image_base64: str, question: str, history: list[dict]) -> str:
    client = _get_client()

    messages: list[dict] = [{"role": "system", "content": config.CHAT_SYSTEM_PROMPT}]
    for i, turn in enumerate(history):
        user_msg: dict = {"role": "user", "content": turn["q"]}
        if i == 0:
            user_msg["images"] = [image_base64]
        messages.append(user_msg)
        messages.append({"role": "assistant", "content": turn["a"]})
    user_msg = {"role": "user", "content": question}
    if not history:
        user_msg["images"] = [image_base64]
    messages.append(user_msg)

    payload = {
        "model": config.VLM_MODEL,
        "messages": messages,
        "stream": False,
    }

    logger.info(
        "chat_followup → POST /api/chat (model=%s, turns=%d, question=%r)",
        config.VLM_MODEL,
        len(history),
        question[:80],
    )

    try:
        resp = await client.post("/api/chat", json=payload)
        resp.raise_for_status()
    except httpx.TimeoutException:
        logger.error("chat_followup timed out after %ds", config.VLM_TIMEOUT_S)
        raise InferenceError(f"Follow-up chat timed out after {config.VLM_TIMEOUT_S}s")
    except httpx.HTTPError as exc:
        logger.error("chat_followup HTTP error: %s", exc)
        raise InferenceError(f"Follow-up chat failed: {exc}") from exc

    body = resp.json()
    answer = body.get("message", {}).get("content", "")
    logger.info("chat_followup ← answer: %s", answer[:200])

    return answer
