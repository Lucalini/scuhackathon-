"""
When MOCK_MODE is True, returns a static test image for laptop development.
picamera2 is only available on Raspberry Pi — mock mode is required for laptops.
"""

from __future__ import annotations

import asyncio
import base64
import io
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator

from PIL import Image

import config

logger = logging.getLogger(__name__)

_FRAME_BOUNDARY = b"FRAME"


def _generate_filename() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    short_id = uuid.uuid4().hex[:4]
    return f"capture_{ts}_{short_id}.jpg"


# Mock implementation (laptop dev)
class _MockCamera:
    """Serves a bundled test image as both stream frames and snapshots."""

    def __init__(self) -> None:
        self._frame_bytes: bytes | None = None

    def start(self) -> None:
        img = Image.open(config.MOCK_IMAGE_PATH)
        img = img.resize(config.CAMERA_RESOLUTION, Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=config.CAMERA_JPEG_QUALITY)
        self._frame_bytes = buf.getvalue()
        logger.info("Mock camera started (image: %s)", config.MOCK_IMAGE_PATH)

    def stop(self) -> None:
        logger.info("Mock camera stopped")

    def get_frame(self) -> bytes:
        assert self._frame_bytes is not None, "Mock camera not started"
        return self._frame_bytes


# Real picamera2 implementation (Raspberry Pi)
class _PiCamera:
    """Wraps picamera2 for MJPEG streaming and snapshot capture."""

    def __init__(self) -> None:
        self._picam2 = None
        self._lock = asyncio.Lock()

    def start(self) -> None:
        from picamera2 import Picamera2  # type: ignore[import-untyped]

        self._picam2 = Picamera2()
        cam_config = self._picam2.create_video_configuration(
            main={"size": config.CAMERA_RESOLUTION, "format": "RGB888"},
        )
        self._picam2.configure(cam_config)
        self._picam2.start()
        logger.info(
            "Pi camera started at %s, JPEG quality %d",
            config.CAMERA_RESOLUTION,
            config.CAMERA_JPEG_QUALITY,
        )

    def stop(self) -> None:
        if self._picam2 is not None:
            self._picam2.stop()
            self._picam2.close()
            logger.info("Pi camera stopped")

    def get_frame(self) -> bytes:
        assert self._picam2 is not None, "Pi camera not started"
        array = self._picam2.capture_array("main")
        img = Image.fromarray(array)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=config.CAMERA_JPEG_QUALITY)
        return buf.getvalue()


# Singleton accessor

_camera_instance: _MockCamera | _PiCamera | None = None


def get_camera() -> _MockCamera | _PiCamera:
    if _camera_instance is None:
        raise RuntimeError("Camera not initialised — call init_camera() at startup")
    return _camera_instance


def init_camera() -> None:
    global _camera_instance  # noqa: PLW0603
    if _camera_instance is not None:
        return

    if config.MOCK_MODE:
        _camera_instance = _MockCamera()
    else:
        _camera_instance = _PiCamera()

    _camera_instance.start()


def shutdown_camera() -> None:
    global _camera_instance  # noqa: PLW0603
    if _camera_instance is not None:
        _camera_instance.stop()
        _camera_instance = None


# Public API

async def mjpeg_stream() -> AsyncGenerator[bytes, None]:
    cam = get_camera()
    interval = 1.0 / config.CAMERA_STREAM_FPS

    while True:
        frame = await asyncio.to_thread(cam.get_frame)
        yield (
            b"--" + _FRAME_BOUNDARY + b"\r\n"
            b"Content-Type: image/jpeg\r\n"
            b"Content-Length: " + str(len(frame)).encode() + b"\r\n"
            b"\r\n" + frame + b"\r\n"
        )
        await asyncio.sleep(interval)


async def capture_snapshot() -> tuple[str, str]:
    cam = get_camera()
    frame = await asyncio.to_thread(cam.get_frame)

    filename = _generate_filename()
    filepath = config.CAPTURES_DIR / filename
    await asyncio.to_thread(filepath.write_bytes, frame)

    b64 = base64.b64encode(frame).decode("ascii")
    logger.info("Snapshot saved: %s (%d bytes)", filename, len(frame))
    return b64, filename
