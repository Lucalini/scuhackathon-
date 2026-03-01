#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
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


def _load_few_shot_images(
    examples: list[dict],
) -> list[tuple[np.ndarray, str]]:
    """Load few-shot example images and pair them with expected responses."""
    loaded: list[tuple[np.ndarray, str]] = []
    for ex in examples:
        path = ex.get("image_path", "")
        response = ex.get("response", "")
        if not path or not response:
            continue
        img = cv2.imread(path)
        if img is None:
            continue
        loaded.append((_convert_resize_image(img), response))
    return loaded


def _run_vlm(
    image_bgr: np.ndarray,
    system_prompt: str,
    user_prompt: str,
    few_shot_examples: list[dict] | None = None,
) -> str:
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

    fs_pairs = _load_few_shot_images(few_shot_examples or [])

    params = VDevice.create_params()
    params.group_id = SHARED_VDEVICE_GROUP_ID
    vdevice = VDevice(params)
    vlm = VLM(vdevice, str(hef_path))
    try:
        frames: list[np.ndarray] = []
        prompt: list[dict] = [
            {"role": "system", "content": [{"type": "text", "text": system_prompt}]},
        ]

        for fs_image, fs_response in fs_pairs:
            frames.append(fs_image)
            prompt.append({
                "role": "user",
                "content": [
                    {"type": "image"},
                    {"type": "text", "text": "Assess this wound."},
                ],
            })
            prompt.append({
                "role": "assistant",
                "content": [{"type": "text", "text": fs_response}],
            })

        query_image = _convert_resize_image(image_bgr)
        frames.append(query_image)
        prompt.append({
            "role": "user",
            "content": [{"type": "image"}, {"type": "text", "text": user_prompt}],
        })

        response = ""
        with vlm.generate(
            prompt=prompt,
            frames=frames,
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


def _infer_severity_from_text(text: str) -> int:
    lowered = text.lower()
    severe_keywords = [
        "severe", "exposed fat", "exposed muscle", "exposed tendon", "exposed bone",
        "heavy bleeding", "uncontrolled bleeding", "full-thickness burn",
        "charred", "crush deformity", "amputation", "life-threatening",
    ]
    moderate_keywords = [
        "moderate", "gaping", "separated edges", "blisters", "pus",
        "red streaking", "penetrating", "foreign body", "infection",
    ]
    minor_keywords = [
        "minor", "bruise", "bruising", "scrape", "abrasion",
        "small cut", "swelling", "superficial",
    ]
    if any(kw in lowered for kw in severe_keywords):
        return 3
    if any(kw in lowered for kw in moderate_keywords):
        return 2
    if any(kw in lowered for kw in minor_keywords):
        return 1
    return 0


def _normalize_triage(answer: str) -> str:
    sev = re.search(r"SEVERITY:\s*([0-3])", answer, re.IGNORECASE)
    conf = re.search(r"CONFIDENCE:\s*([^\n\r]+)", answer, re.IGNORECASE)
    reason = re.search(r"REASONING:\s*(.+)", answer, re.IGNORECASE | re.DOTALL)
    if sev and conf and reason:
        nums = [int(x) for x in re.findall(r"\d{1,3}", conf.group(1))]
        conf_value = max(0, min(100, nums[0] if nums else 50))
        reasoning = " ".join(reason.group(1).split())
        return (
            f"SEVERITY: {sev.group(1)}\n"
            f"CONFIDENCE: {conf_value}\n"
            f"REASONING: {reasoning}"
        )

    cleaned = " ".join(answer.split())
    inferred_sev = _infer_severity_from_text(cleaned) if cleaned else 0
    conf_value = 50 if sev is None else 70
    if sev:
        inferred_sev = int(sev.group(1))
    return (
        f"SEVERITY: {inferred_sev}\n"
        f"CONFIDENCE: {conf_value}\n"
        f"REASONING: {cleaned[:220] if cleaned else 'Model returned non-structured output.'}"
    )


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        image_path = str(payload.get("image_path", "")).strip()
        prompt = str(payload.get("prompt", "")).strip()
        if not image_path:
            raise RuntimeError("image_path is required")

        image = cv2.imread(image_path)
        if image is None:
            raise RuntimeError(f"Could not read image at: {image_path}")

        system_prompt = os.getenv(
            "HAILO_BACKEND_SYSTEM_PROMPT",
            "You are a field medical triage assistant. Follow output format exactly.",
        )
        if not prompt:
            prompt = (
                "Respond EXACTLY in this format:\n"
                "SEVERITY: <0|1|2|3>\n"
                "CONFIDENCE: <0-100>\n"
                "REASONING: <one concise sentence>"
            )

        few_shot_examples = payload.get("few_shot_examples", [])
        answer = _run_vlm(image, system_prompt, prompt, few_shot_examples)
        triage_text = _normalize_triage(answer)
        sys.stdout.write(json.dumps({"response": triage_text}))
        return 0
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"hailo_direct_assess error: {exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
