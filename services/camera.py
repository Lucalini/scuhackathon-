"""
Camera service — picamera2 MJPEG stream + snapshot capture.

Provides:
    - mjpeg_stream()      → async generator yielding JPEG frames
    - capture_snapshot()   → base64-encoded JPEG string

When MOCK_MODE is True, returns a static test image for laptop development.

Assigned to: BE-3
"""
