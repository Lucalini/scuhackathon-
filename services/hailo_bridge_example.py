"""
Example Hailo bridge module with practical defaults.

This bridge supports two integration modes:
1) HTTP mode: call a local Hailo service endpoint.
2) Command mode: execute a local command that reads JSON from stdin.

Set:
    export HAILO_MODULE=services.hailo_bridge_example
    export HAILO_ASSESS_CALLABLE=assess_wound
    export HAILO_CHAT_CALLABLE=chat_followup

HTTP mode env vars:
    export HAILO_ASSESS_URL=http://127.0.0.1:9001/assess
    export HAILO_CHAT_URL=http://127.0.0.1:9001/chat

Command mode env vars:
    export HAILO_ASSESS_COMMAND="python /path/to/bridge_assess.py"
    export HAILO_CHAT_COMMAND="python /path/to/bridge_chat.py"

Command mode contract:
    - stdin: JSON payload (includes image_base64 and temp image_path)
    - stdout: either plain text, or JSON with response fields:
      assess: response|text OR severity+confidence+reasoning
      chat:   answer|response|message
"""

from __future__ import annotations

import base64
import json
import os
import shlex
import subprocess
import tempfile
from pathlib import Path
from urllib import request


def _timeout_s() -> int:
    return int(os.getenv("HAILO_BRIDGE_TIMEOUT_S", "120"))


def _decode_to_temp_jpg(image_base64: str) -> Path:
    raw = base64.b64decode(image_base64.encode("ascii"))
    tmp = tempfile.NamedTemporaryFile(prefix="hailo_bridge_", suffix=".jpg", delete=False)
    try:
        tmp.write(raw)
    finally:
        tmp.close()
    return Path(tmp.name)


def _extract_text(payload: dict, keys: list[str]) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    message = payload.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
    return None


def _format_triage_text(payload: dict) -> str | None:
    sev = payload.get("severity")
    conf = payload.get("confidence")
    reasoning = payload.get("reasoning")
    if sev is None or conf is None or reasoning is None:
        return None
    return (
        f"SEVERITY: {int(sev)}\n"
        f"CONFIDENCE: {int(float(conf))}\n"
        f"REASONING: {str(reasoning).strip()}"
    )


def _http_post_json(url: str, payload: dict) -> dict | str:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=_timeout_s()) as resp:  # noqa: S310
        raw = resp.read().decode("utf-8")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _run_command(command_str: str, payload: dict) -> dict | str:
    args = shlex.split(command_str)
    if not args:
        raise RuntimeError("Empty command configured for Hailo bridge")
    proc = subprocess.run(
        args,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=_timeout_s(),
        check=False,
    )
    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        raise RuntimeError(f"Bridge command failed (exit={proc.returncode}): {stderr}")

    out = (proc.stdout or "").strip()
    if not out:
        raise RuntimeError("Bridge command returned empty stdout")
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return out


def _call_assess_backend(payload: dict) -> dict | str:
    assess_url = os.getenv("HAILO_ASSESS_URL", "").strip()
    assess_cmd = os.getenv("HAILO_ASSESS_COMMAND", "").strip()
    if assess_url:
        return _http_post_json(assess_url, payload)
    if assess_cmd:
        return _run_command(assess_cmd, payload)
    raise RuntimeError("Set HAILO_ASSESS_URL or HAILO_ASSESS_COMMAND for assess_wound")


def _call_chat_backend(payload: dict) -> dict | str:
    chat_url = os.getenv("HAILO_CHAT_URL", "").strip()
    chat_cmd = os.getenv("HAILO_CHAT_COMMAND", "").strip()
    if chat_url:
        return _http_post_json(chat_url, payload)
    if chat_cmd:
        return _run_command(chat_cmd, payload)
    raise RuntimeError("Set HAILO_CHAT_URL or HAILO_CHAT_COMMAND for chat_followup")


def assess_wound(image_base64: str, prompt: str, model: str) -> str:
    image_path = _decode_to_temp_jpg(image_base64)
    try:
        payload = {
            "model": model,
            "prompt": prompt,
            "image_base64": image_base64,
            "image_path": str(image_path),
        }
        result = _call_assess_backend(payload)
        if isinstance(result, str):
            return result

        text = _extract_text(result, ["response", "text", "answer"])
        if text:
            return text

        triage_text = _format_triage_text(result)
        if triage_text:
            return triage_text

        raise RuntimeError("Assess backend response missing usable output fields")
    finally:
        try:
            image_path.unlink(missing_ok=True)
        except OSError:
            pass


def chat_followup(
    image_base64: str,
    question: str,
    history: list[dict],
    system_prompt: str,
    model: str,
) -> str:
    image_path = _decode_to_temp_jpg(image_base64)
    try:
        payload = {
            "model": model,
            "system_prompt": system_prompt,
            "question": question,
            "history": history,
            "image_base64": image_base64,
            "image_path": str(image_path),
        }
        result = _call_chat_backend(payload)
        if isinstance(result, str):
            return result

        text = _extract_text(result, ["answer", "response", "text"])
        if text:
            return text
        raise RuntimeError("Chat backend response missing usable output fields")
    finally:
        try:
            image_path.unlink(missing_ok=True)
        except OSError:
            pass
