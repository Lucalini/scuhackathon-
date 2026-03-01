#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys

from services.hailo_vlm_cli import BridgeCliError, run_vlm_interactive


def _to_triage_text(raw: str) -> str:
    sev = re.search(r"SEVERITY:\s*([0-3])", raw, re.IGNORECASE)
    conf = re.search(r"CONFIDENCE:\s*(\d{1,3})", raw, re.IGNORECASE)
    reason = re.search(r"REASONING:\s*(.+)", raw, re.IGNORECASE | re.DOTALL)
    if sev and conf and reason:
        return (
            f"SEVERITY: {sev.group(1)}\n"
            f"CONFIDENCE: {min(100, int(conf.group(1)))}\n"
            f"REASONING: {reason.group(1).strip()}"
        )
    raise BridgeCliError(
        "Model output missing required triage fields (SEVERITY/CONFIDENCE/REASONING)"
    )


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        prompt = payload.get("prompt", "")
        image_path = payload.get("image_path", "")
        if not prompt or not image_path:
            raise BridgeCliError("Payload must include non-empty 'prompt' and 'image_path'")

        raw = run_vlm_interactive(prompt=prompt, image_path=image_path)
        triage_text = _to_triage_text(raw)
        sys.stdout.write(json.dumps({"response": triage_text}))
        return 0
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"bridge_assess error: {exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
