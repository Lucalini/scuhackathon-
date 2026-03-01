from __future__ import annotations

import re


class InferenceError(Exception):
    """Raised when the inference backend call fails."""


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
