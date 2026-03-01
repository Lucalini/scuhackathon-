from __future__ import annotations

import os
import re
import select
import shlex
import subprocess
import time
from pathlib import Path


class BridgeCliError(RuntimeError):
    """Raised when the interactive VLM CLI cannot be driven reliably."""


def _token(name: str, default: str) -> str:
    return os.getenv(name, default).strip().lower()


def _extract_answer(output: str) -> str:
    answer_prefix = os.getenv("HAILO_VLM_ANSWER_PREFIX", "assistant:")
    if answer_prefix:
        pattern = re.compile(re.escape(answer_prefix), re.IGNORECASE)
        matches = list(pattern.finditer(output))
        if matches:
            tail = output[matches[-1].end() :].strip()
            if tail:
                return tail

    lines = [ln.strip() for ln in output.splitlines() if ln.strip()]
    for line in reversed(lines):
        lowered = line.lower()
        if lowered.startswith("please provide"):
            continue
        if "using the" in lowered and "--input" in lowered:
            continue
        if lowered.startswith("warning"):
            continue
        return line
    raise BridgeCliError("Unable to extract answer text from VLM output")


def run_vlm_interactive(prompt: str, image_path: str) -> str:
    cmd = os.getenv("HAILO_VLM_CHAT_COMMAND", "python vlm_chat.py --input rpi").strip()
    cwd = os.getenv("HAILO_VLM_CHAT_CWD", "").strip() or str(Path.cwd())
    total_timeout_s = int(os.getenv("HAILO_VLM_TOTAL_TIMEOUT_S", "180"))
    idle_after_inputs_s = int(os.getenv("HAILO_VLM_IDLE_AFTER_INPUTS_S", "8"))

    image_token = _token("HAILO_VLM_IMAGE_PROMPT_TOKEN", "image")
    question_token = _token("HAILO_VLM_QUESTION_PROMPT_TOKEN", "question")
    done_token = _token("HAILO_VLM_DONE_TOKEN", "")

    args = shlex.split(cmd)
    if not args:
        raise BridgeCliError("HAILO_VLM_CHAT_COMMAND is empty")

    proc = subprocess.Popen(
        args,
        cwd=cwd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    if proc.stdin is None or proc.stdout is None:
        raise BridgeCliError("Failed to create interactive subprocess pipes")

    prompt_one_line = " ".join(prompt.split())
    output = ""
    image_sent = False
    question_sent = False
    start = time.monotonic()
    last_output_at = start

    try:
        while True:
            now = time.monotonic()
            if now - start > total_timeout_s:
                raise BridgeCliError("VLM command timed out")

            ready, _, _ = select.select([proc.stdout], [], [], 0.25)
            chunk = ""
            if ready:
                chunk = proc.stdout.read(1)
                if chunk:
                    output += chunk
                    last_output_at = now

            lowered = output.lower()
            if (not image_sent) and image_token and (image_token in lowered):
                proc.stdin.write(str(image_path).strip() + "\n")
                proc.stdin.flush()
                image_sent = True
            if (not question_sent) and question_token and (question_token in lowered):
                proc.stdin.write(prompt_one_line + "\n")
                proc.stdin.flush()
                question_sent = True

            if done_token and done_token in lowered:
                break

            if image_sent and question_sent and (now - last_output_at) > idle_after_inputs_s:
                break

            if proc.poll() is not None:
                break
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()

    if proc.returncode not in (0, None):
        raise BridgeCliError(
            f"VLM command failed (exit={proc.returncode}). Output tail: {output[-400:]}"
        )

    return _extract_answer(output)
