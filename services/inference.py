"""
Inference service — Hailo-Ollama REST client for Qwen2-VL-2B-Instruct.

Provides:
    - assess_wound(image_b64)                → {severity, confidence, reasoning}
    - chat_followup(image_b64, question, history) → str
    - parse_vlm_response(text)               → {severity, confidence, reasoning}

When MOCK_MODE is True, returns hardcoded/random results for laptop testing.

Assigned to: BE-5
"""
