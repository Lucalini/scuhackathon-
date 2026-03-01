"""
Sensor service — DS18B20 temperature + push-button GPIO.

Provides:
    - read_temperature()   → float (Celsius)
    - ButtonListener class → gpiozero callback on press

When MOCK_MODE is True, returns random temp values (36.0–38.5) and
exposes a simulated button press via API.

Assigned to: BE-4
"""
