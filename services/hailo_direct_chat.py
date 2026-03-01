#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys

import cv2
import numpy as np
from hailo_platform import VDevice
from hailo_platform.genai import VLM
from hailo_apps.python.core.common.core import resolve_hef_path
from hailo_apps.python.core.common.defines import (
    HAILO10H_ARCH,
    SHARED_VDEVICE_GROUP_ID,
    VLM_CHAT_APP,
)


def _target_size() -> tuple[int, int]:
    size = int(os.getenv("HAILO_VLM_INPUT_SIZE", "336"))
    return (size, size)


def _convert_resize_image(image_array: np.ndarray, target_size: tuple[int, int] | None = None) -> np.ndarray:
    if target_size is None:
        target_size = _target_size()
    if len(image_array.shape) == 3 and image_array.shape[2] == 3:
        image_array = cv2.cvtColor(image_array, cv2.COLOR_BGR2RGB)

    h, w = image_array.shape[:2]
    target_w, target_h = target_size
    scale = min(target_w / w, target_h / h)
    new_w = int(w * scale)
    new_h = int(h * scale)
    interpolation = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC
    resized = cv2.resize(image_array, (new_w, new_h), interpolation=interpolation)
    canvas = np.zeros((target_h, target_w, 3), dtype=np.uint8)
    x_start = (target_w - new_w) // 2
    y_start = (target_h - new_h) // 2
    canvas[y_start : y_start + new_h, x_start : x_start + new_w] = resized
    return canvas


def _build_user_prompt(history: list[dict], question: str) -> str:
    parts: list[str] = []
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


def _run_vlm(image_bgr: np.ndarray, system_prompt: str, user_prompt: str) -> str:
    hef_path = resolve_hef_path(
        os.getenv("HAILO_HEF_PATH") or None,
        app_name=VLM_CHAT_APP,
        arch=HAILO10H_ARCH,
    )
    if hef_path is None:
        raise RuntimeError("Failed to resolve HEF path")

    max_tokens = int(os.getenv("HAILO_BACKEND_MAX_TOKENS", "220"))
    temperature = float(os.getenv("HAILO_BACKEND_TEMPERATURE", "0.1"))
    seed = int(os.getenv("HAILO_BACKEND_SEED", "42"))

    params = VDevice.create_params()
    params.group_id = SHARED_VDEVICE_GROUP_ID
    vdevice = VDevice(params)
    vlm = VLM(vdevice, str(hef_path))
    try:
        image = _convert_resize_image(image_bgr)
        prompt = [
            {"role": "system", "content": [{"type": "text", "text": system_prompt}]},
            {
                "role": "user",
                "content": [{"type": "image"}, {"type": "text", "text": user_prompt}],
            },
        ]
        response = ""
        with vlm.generate(
            prompt=prompt,
            frames=[image],
            temperature=temperature,
            seed=seed,
            max_generated_tokens=max_tokens,
        ) as generation:
            for chunk in generation:
                if chunk != "<|im_end|>":
                    response += chunk
        vlm.clear_context()
        return response.strip()
    finally:
        try:
            vlm.release()
        finally:
            vdevice.release()


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        image_path = str(payload.get("image_path", "")).strip()
        question = str(payload.get("question", "")).strip()
        history = payload.get("history", [])
        system_prompt = str(payload.get("system_prompt", "")).strip()
        if not image_path or not question:
            raise RuntimeError("image_path and question are required")
        if not isinstance(history, list):
            raise RuntimeError("history must be a list")

        image = cv2.imread(image_path)
        if image is None:
            raise RuntimeError(f"Could not read image at: {image_path}")
        if not system_prompt:
            system_prompt = (
                "You are a concise field triage assistant. "
                "Provide practical, direct advice in two sentences max."
            )

        user_prompt = _build_user_prompt(history, question)
        answer = _run_vlm(image, system_prompt, user_prompt)
        answer = " ".join(answer.split())
        if answer.lower().startswith("user:"):
            answer = answer[5:].strip()
        if answer.lower().startswith("assistant:"):
            answer = answer[10:].strip()
        if not answer:
            answer = "No model response available."
        sys.stdout.write(json.dumps({"answer": answer}))
        return 0
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"hailo_direct_chat error: {exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
