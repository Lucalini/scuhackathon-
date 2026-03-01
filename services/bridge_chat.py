#!/usr/bin/env python3
from __future__ import annotations

import json
import sys

from services.hailo_vlm_cli import BridgeCliError, run_vlm_interactive


def _build_chat_prompt(system_prompt: str, history: list[dict], question: str) -> str:
    parts: list[str] = []
    if system_prompt:
        parts.append(system_prompt.strip())
    for turn in history:
        q = str(turn.get("q", "")).strip()
        a = str(turn.get("a", "")).strip()
        if q:
            parts.append(f"User: {q}")
        if a:
            parts.append(f"Assistant: {a}")
    parts.append(f"User: {question.strip()}")
    parts.append("Assistant:")
    return "\n".join(parts)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        question = str(payload.get("question", "")).strip()
        image_path = str(payload.get("image_path", "")).strip()
        history = payload.get("history", [])
        system_prompt = str(payload.get("system_prompt", "")).strip()
        if not question or not image_path:
            raise BridgeCliError("Payload must include non-empty 'question' and 'image_path'")
        if not isinstance(history, list):
            raise BridgeCliError("'history' must be a list")

        prompt = _build_chat_prompt(system_prompt, history, question)
        answer = run_vlm_interactive(prompt=prompt, image_path=image_path)
        sys.stdout.write(json.dumps({"answer": answer}))
        return 0
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"bridge_chat error: {exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
