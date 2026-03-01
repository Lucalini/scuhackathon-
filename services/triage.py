"""
Triage service — orchestration layer.

Provides:
    - perform_triage()     → capture → temp → VLM assess → escalation check → DB save
    - should_escalate()    → (bool, reason_string)

Wires together camera, sensors, inference, and database modules.

Assigned to: BE-6
"""
