import os
import json
import time
import base64
import threading
from datetime import datetime
from flask import Flask, render_template, jsonify, request, Response

app = Flask(__name__)

sensor_log = []
temperature_history = []
vlm_chat_history = []

camera_active = False
latest_frame = None
frame_lock = threading.Lock()


def read_temperature():
    """Read from Inland KS0329 temperature sensor via GPIO/I2C."""
    try:
        # KS0329 uses DS18B20 — read from 1-wire interface
        base_dir = "/sys/bus/w1/devices/"
        if os.path.exists(base_dir):
            for folder in os.listdir(base_dir):
                if folder.startswith("28-"):
                    device_file = os.path.join(base_dir, folder, "w1_slave")
                    with open(device_file, "r") as f:
                        lines = f.readlines()
                    if lines[0].strip().endswith("YES"):
                        pos = lines[1].find("t=")
                        if pos != -1:
                            temp_c = float(lines[1][pos + 2 :]) / 1000.0
                            temp_f = temp_c * 9.0 / 5.0 + 32.0
                            return round(temp_c, 1), round(temp_f, 1)
    except Exception as e:
        log_sensor_event(f"Temp sensor error: {e}")
    return None, None


def log_sensor_event(message):
    entry = {"time": datetime.now().strftime("%H:%M:%S"), "message": message}
    sensor_log.append(entry)
    if len(sensor_log) > 100:
        sensor_log.pop(0)


def run_vlm_inference(image_b64, prompt):
    """Run Qwen2-VL inference via the AI HAT+ or local model server."""
    try:
        import requests

        response = requests.post(
            "http://localhost:8000/v1/chat/completions",
            json={
                "model": "Qwen2-VL-7B-Instruct",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
                            },
                            {"type": "text", "text": prompt},
                        ],
                    }
                ],
                "max_tokens": 512,
            },
            timeout=60,
        )
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"VLM Error: {str(e)}"


def run_vlm_text_only(prompt):
    """Run text-only VLM inference."""
    try:
        import requests

        response = requests.post(
            "http://localhost:8000/v1/chat/completions",
            json={
                "model": "Qwen2-VL-7B-Instruct",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 512,
            },
            timeout=60,
        )
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"VLM Error: {str(e)}"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/temperature")
def get_temperature():
    temp_c, temp_f = read_temperature()
    timestamp = datetime.now().strftime("%H:%M:%S")

    if temp_c is not None:
        entry = {"time": timestamp, "temp_c": temp_c, "temp_f": temp_f}
        temperature_history.append(entry)
        if len(temperature_history) > 60:
            temperature_history.pop(0)
        return jsonify({"status": "ok", "temp_c": temp_c, "temp_f": temp_f, "time": timestamp})

    return jsonify({"status": "no_sensor", "temp_c": None, "temp_f": None, "time": timestamp})


@app.route("/api/temperature/history")
def get_temperature_history():
    return jsonify(temperature_history)


@app.route("/api/sensor/log")
def get_sensor_log():
    return jsonify(sensor_log[-20:])


@app.route("/api/camera/capture", methods=["POST"])
def camera_capture():
    """Capture a frame from the Pi camera."""
    try:
        from picamera2 import Picamera2

        picam = Picamera2()
        config = picam.create_still_configuration(main={"size": (640, 480)})
        picam.configure(config)
        picam.start()
        time.sleep(0.5)

        import io
        from PIL import Image

        arr = picam.capture_array()
        picam.stop()
        picam.close()

        img = Image.fromarray(arr)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        img_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

        log_sensor_event("Camera: Frame captured")
        return jsonify({"status": "ok", "image": img_b64})
    except ImportError:
        log_sensor_event("Camera: picamera2 not available")
        return jsonify({"status": "error", "message": "picamera2 not installed"})
    except Exception as e:
        log_sensor_event(f"Camera error: {e}")
        return jsonify({"status": "error", "message": str(e)})


@app.route("/api/vlm/analyze", methods=["POST"])
def vlm_analyze():
    """Send image + prompt to VLM for analysis."""
    data = request.json
    image_b64 = data.get("image", "")
    prompt = data.get("prompt", "Describe what you see in this medical image. Identify any visible conditions or concerns.")

    if image_b64:
        response_text = run_vlm_inference(image_b64, prompt)
    else:
        response_text = run_vlm_text_only(prompt)

    entry = {
        "role": "assistant",
        "content": response_text,
        "time": datetime.now().strftime("%H:%M:%S"),
    }
    vlm_chat_history.append(entry)

    log_sensor_event("VLM: Analysis complete")
    return jsonify({"status": "ok", "response": response_text})


@app.route("/api/vlm/chat", methods=["POST"])
def vlm_chat():
    """Send a text message to the VLM."""
    data = request.json
    message = data.get("message", "")

    user_entry = {
        "role": "user",
        "content": message,
        "time": datetime.now().strftime("%H:%M:%S"),
    }
    vlm_chat_history.append(user_entry)

    response_text = run_vlm_text_only(message)

    assistant_entry = {
        "role": "assistant",
        "content": response_text,
        "time": datetime.now().strftime("%H:%M:%S"),
    }
    vlm_chat_history.append(assistant_entry)

    return jsonify({"status": "ok", "response": response_text})


@app.route("/api/vlm/history")
def vlm_history():
    return jsonify(vlm_chat_history[-50:])


@app.route("/api/readings/reset", methods=["POST"])
def reset_readings():
    temperature_history.clear()
    sensor_log.clear()
    vlm_chat_history.clear()
    log_sensor_event("System: All readings reset")
    return jsonify({"status": "ok"})


@app.route("/api/status")
def system_status():
    """System health check."""
    camera_ok = False
    vlm_ok = False

    try:
        from picamera2 import Picamera2
        camera_ok = True
    except ImportError:
        pass

    try:
        import requests
        r = requests.get("http://localhost:8000/v1/models", timeout=2)
        vlm_ok = r.status_code == 200
    except Exception:
        pass

    temp_c, _ = read_temperature()

    return jsonify({
        "camera": camera_ok,
        "vlm": vlm_ok,
        "temp_sensor": temp_c is not None,
        "time": datetime.now().strftime("%H:%M:%S"),
    })


if __name__ == "__main__":
    log_sensor_event("System: VI Triage started")
    app.run(host="0.0.0.0", port=8080, debug=False)
