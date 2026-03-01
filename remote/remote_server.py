"""
Remote doctor server — FastAPI app (separate instance, same codebase pattern).

Endpoints:
    POST /api/entries             — receive synced entry from Pi
    GET  /api/entries             — list escalated entries
    GET  /api/entries/{id}        — single entry with image
    POST /api/entries/{id}/guidance — doctor sends guidance text
    GET  /api/entries/{id}/guidance — Pi polls for guidance

Assigned to: STRETCH-A
"""
