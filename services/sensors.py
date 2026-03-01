from __future__ import annotations

import glob
import logging
import random
import threading
import time

import config

logger = logging.getLogger(__name__)

_TEMP_TTL_S = 2.0


class _MockTemperatureSensor:
    """Return random body-temperature values for laptop development."""

    def __init__(self) -> None:
        self._last_value: float | None = None
        self._last_read: float = 0.0

    def read(self) -> float | None:
        now = time.monotonic()
        if self._last_value is not None and (now - self._last_read) < _TEMP_TTL_S:
            return self._last_value
        self._last_value = round(random.uniform(36.0, 38.5), 1)
        self._last_read = now
        logger.debug("Mock temperature: %.1f °C", self._last_value)
        return self._last_value


class _PiTemperatureSensor:
    """Read DS18B20 via 1-Wire sysfs with a TTL cache."""

    def __init__(self) -> None:
        self._device_path: str | None = None
        self._last_value: float | None = None
        self._last_read: float = 0.0
        self._lock = threading.Lock()
        self._discover_device()

    def _discover_device(self) -> None:
        matches = glob.glob(config.DS18B20_BASE_DIR + "28-*/w1_slave")
        if matches:
            self._device_path = matches[0]
            logger.info("DS18B20 found: %s", self._device_path)
        else:
            logger.warning("DS18B20 not found under %s", config.DS18B20_BASE_DIR)

    def read(self) -> float | None:
        with self._lock:
            now = time.monotonic()
            if self._last_value is not None and (now - self._last_read) < _TEMP_TTL_S:
                return self._last_value

            if self._device_path is None:
                self._discover_device()
                if self._device_path is None:
                    return None

            try:
                with open(self._device_path) as f:
                    lines = f.readlines()
            except OSError:
                logger.exception("Failed to read DS18B20 at %s", self._device_path)
                return self._last_value

            if len(lines) < 2 or "YES" not in lines[0]:
                logger.warning("DS18B20 CRC check failed")
                return self._last_value

            pos = lines[1].find("t=")
            if pos == -1:
                logger.warning("DS18B20 output missing t= field")
                return self._last_value

            raw = lines[1][pos + 2:].strip()
            self._last_value = round(int(raw) / 1000.0, 1)
            self._last_read = now
            logger.debug("DS18B20 temperature: %.1f °C", self._last_value)
            return self._last_value


class _MockButtonListener:
    """Tracks simulated button presses triggered via the debug API."""

    def __init__(self) -> None:
        self._pressed = False
        self._lock = threading.Lock()

    def start(self) -> None:
        logger.info("Mock button listener started (use POST /api/debug/button-press)")

    def stop(self) -> None:
        logger.info("Mock button listener stopped")

    def simulate_press(self) -> None:
        with self._lock:
            self._pressed = True
        logger.info("Mock button press simulated")

    def was_pressed(self) -> bool:
        with self._lock:
            pressed = self._pressed
            self._pressed = False
            return pressed


class _PiButtonListener:
    """Detect physical button press on GPIO via gpiozero."""

    def __init__(self, pin: int) -> None:
        self._pin = pin
        self._pressed = False
        self._lock = threading.Lock()
        self._button = None

    def start(self) -> None:
        from gpiozero import Button  # type: ignore[import-untyped]

        self._button = Button(self._pin, pull_up=True, bounce_time=0.05)
        self._button.when_pressed = self._on_press
        logger.info("Pi button listener started on GPIO %d", self._pin)

    def stop(self) -> None:
        if self._button is not None:
            self._button.close()
            self._button = None
            logger.info("Pi button listener stopped")

    def _on_press(self) -> None:
        with self._lock:
            self._pressed = True
        logger.info("Physical button pressed on GPIO %d", self._pin)

    def simulate_press(self) -> None:
        """Allow debug endpoint to work even on the Pi."""
        with self._lock:
            self._pressed = True
        logger.info("Button press simulated via debug API (Pi mode)")

    def was_pressed(self) -> bool:
        with self._lock:
            pressed = self._pressed
            self._pressed = False
            return pressed


# Singleton management

_temp_sensor: _MockTemperatureSensor | _PiTemperatureSensor | None = None
_button_listener: _MockButtonListener | _PiButtonListener | None = None


def init_sensors() -> None:
    """Initialise temperature sensor and button listener. Call once at app startup."""
    global _temp_sensor, _button_listener  # noqa: PLW0603

    if _temp_sensor is not None:
        return

    if config.MOCK_MODE:
        _temp_sensor = _MockTemperatureSensor()
        _button_listener = _MockButtonListener()
    else:
        _temp_sensor = _PiTemperatureSensor()
        _button_listener = _PiButtonListener(config.GPIO_BUTTON_PIN)

    _button_listener.start()
    logger.info("Sensors initialised (mock_mode=%s)", config.MOCK_MODE)


def shutdown_sensors() -> None:
    """Stop sensor services. Call at app shutdown."""
    global _temp_sensor, _button_listener  # noqa: PLW0603
    if _button_listener is not None:
        _button_listener.stop()
        _button_listener = None
    _temp_sensor = None


# Public API

def _get_temp_sensor() -> _MockTemperatureSensor | _PiTemperatureSensor:
    if _temp_sensor is None:
        raise RuntimeError("Sensors not initialised — call init_sensors() at startup")
    return _temp_sensor


def _get_button_listener() -> _MockButtonListener | _PiButtonListener:
    if _button_listener is None:
        raise RuntimeError("Sensors not initialised — call init_sensors() at startup")
    return _button_listener


def read_temperature() -> float | None:
    """Return the current DS18B20 temperature in Celsius, or None on failure."""
    return _get_temp_sensor().read()


def was_button_pressed() -> bool:
    """Return True if the button was pressed since the last check (resets flag)."""
    return _get_button_listener().was_pressed()


def simulate_button_press() -> None:
    """Simulate a button press via the debug API (works in both mock and Pi mode)."""
    _get_button_listener().simulate_press()
