/* ===== VI Triage — Frontend Application ===== */

(function () {
  "use strict";

  // ── State ──
  let capturedImage = null;
  let tempChart = null;
  let keyboardTarget = null;
  let shiftActive = false;

  // ── DOM refs ──
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => document.querySelectorAll(sel);

  const els = {
    clock: $("#clock"),
    cameraViewport: $("#camera-viewport"),
    cameraPlaceholder: $("#camera-placeholder"),
    cameraPreview: $("#camera-preview"),
    btnCapture: $("#btn-capture"),
    btnUploadVlm: $("#btn-upload-vlm"),
    btnResetCapture: $("#btn-reset-capture"),
    chatMessages: $("#chat-messages"),
    chatInput: $("#chat-input"),
    btnSend: $("#btn-send"),
    tempValue: $("#temp-value"),
    tempChart: $("#temp-chart"),
    logEntries: $("#log-entries"),
    btnResetAll: $("#btn-reset-all"),
    keyboardOverlay: $("#keyboard-overlay"),
    keyboard: $("#keyboard"),
    loadingOverlay: $("#loading-overlay"),
    loadingText: $("#loading-text"),
    statusCam: $("#status-cam"),
    statusVlm: $("#status-vlm"),
    statusTemp: $("#status-temp"),
  };

  // ── Clock ──
  function updateClock() {
    const now = new Date();
    els.clock.textContent = now.toLocaleTimeString("en-US", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });
  }

  // ── Loading ──
  function showLoading(text) {
    els.loadingText.textContent = text || "Processing...";
    els.loadingOverlay.classList.remove("hidden");
  }

  function hideLoading() {
    els.loadingOverlay.classList.add("hidden");
  }

  // ── API helpers ──
  async function api(endpoint, options = {}) {
    try {
      const res = await fetch(endpoint, {
        headers: { "Content-Type": "application/json" },
        ...options,
      });
      return await res.json();
    } catch (e) {
      console.error(`API error [${endpoint}]:`, e);
      return { status: "error", message: e.message };
    }
  }

  // ── Camera ──
  async function captureFrame() {
    showLoading("Capturing...");
    const data = await api("/api/camera/capture", { method: "POST" });
    hideLoading();

    if (data.status === "ok" && data.image) {
      capturedImage = data.image;
      els.cameraPreview.src = `data:image/jpeg;base64,${data.image}`;
      els.cameraPreview.classList.remove("hidden");
      els.cameraPlaceholder.classList.add("hidden");
      addLogEntry("Camera: Frame captured");
    } else {
      addLogEntry(`Camera: ${data.message || "Capture failed"}`);
    }
  }

  function resetCapture() {
    capturedImage = null;
    els.cameraPreview.classList.add("hidden");
    els.cameraPreview.src = "";
    els.cameraPlaceholder.classList.remove("hidden");
    addLogEntry("Camera: Preview reset");
  }

  // ── VLM ──
  async function analyzeWithVlm() {
    if (!capturedImage) {
      addLogEntry("VLM: No image captured");
      return;
    }

    showLoading("Analyzing image...");
    const data = await api("/api/vlm/analyze", {
      method: "POST",
      body: JSON.stringify({ image: capturedImage }),
    });
    hideLoading();

    if (data.status === "ok") {
      appendChatMessage("assistant", data.response);
    } else {
      appendChatMessage("assistant", "Analysis failed. Check VLM connection.");
    }
  }

  async function sendChatMessage() {
    const text = els.chatInput.value.trim();
    if (!text) return;

    appendChatMessage("user", text);
    els.chatInput.value = "";
    closeKeyboard();

    showLoading("Thinking...");
    const data = await api("/api/vlm/chat", {
      method: "POST",
      body: JSON.stringify({ message: text }),
    });
    hideLoading();

    if (data.status === "ok") {
      appendChatMessage("assistant", data.response);
    } else {
      appendChatMessage("assistant", "Error: Could not reach VLM.");
    }
  }

  function appendChatMessage(role, content) {
    const welcome = els.chatMessages.querySelector(".chat-welcome");
    if (welcome) welcome.remove();

    const msg = document.createElement("div");
    msg.className = `chat-msg ${role}`;

    const textEl = document.createElement("div");
    textEl.textContent = content;
    msg.appendChild(textEl);

    const timeEl = document.createElement("div");
    timeEl.className = "chat-msg-time";
    timeEl.textContent = new Date().toLocaleTimeString("en-US", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
    msg.appendChild(timeEl);

    els.chatMessages.appendChild(msg);
    els.chatMessages.scrollTop = els.chatMessages.scrollHeight;
  }

  // ── Temperature Chart ──
  function initTempChart() {
    const ctx = els.tempChart.getContext("2d");
    tempChart = new Chart(ctx, {
      type: "line",
      data: {
        labels: [],
        datasets: [
          {
            label: "°C",
            data: [],
            borderColor: "#4fc3f7",
            backgroundColor: "rgba(79,195,247,0.08)",
            borderWidth: 1.5,
            pointRadius: 0,
            tension: 0.3,
            fill: true,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 300 },
        plugins: {
          legend: { display: false },
        },
        scales: {
          x: {
            display: true,
            ticks: {
              color: "#8b8fa3",
              font: { size: 8 },
              maxTicksLimit: 6,
              maxRotation: 0,
            },
            grid: { color: "rgba(46,51,72,0.5)" },
          },
          y: {
            display: true,
            ticks: {
              color: "#8b8fa3",
              font: { size: 9 },
              maxTicksLimit: 5,
            },
            grid: { color: "rgba(46,51,72,0.5)" },
            suggestedMin: 34,
            suggestedMax: 42,
          },
        },
      },
    });
  }

  async function pollTemperature() {
    const data = await api("/api/temperature");
    if (data.temp_c !== null) {
      els.tempValue.textContent = data.temp_c.toFixed(1);

      tempChart.data.labels.push(data.time);
      tempChart.data.datasets[0].data.push(data.temp_c);

      if (tempChart.data.labels.length > 30) {
        tempChart.data.labels.shift();
        tempChart.data.datasets[0].data.shift();
      }
      tempChart.update("none");
    }
  }

  // ── Sensor Log ──
  function addLogEntry(message) {
    const emptyEl = els.logEntries.querySelector(".log-empty");
    if (emptyEl) emptyEl.remove();

    const entry = document.createElement("div");
    entry.className = "log-entry";

    const time = document.createElement("span");
    time.className = "log-time";
    time.textContent = new Date().toLocaleTimeString("en-US", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });

    const msg = document.createElement("span");
    msg.className = "log-msg";
    msg.textContent = message;

    entry.appendChild(time);
    entry.appendChild(msg);
    els.logEntries.appendChild(entry);
    els.logEntries.scrollTop = els.logEntries.scrollHeight;
  }

  async function pollSensorLog() {
    const data = await api("/api/sensor/log");
    if (Array.isArray(data) && data.length > 0) {
      els.logEntries.innerHTML = "";
      data.forEach((entry) => {
        const el = document.createElement("div");
        el.className = "log-entry";
        el.innerHTML = `<span class="log-time">${entry.time}</span><span class="log-msg">${entry.message}</span>`;
        els.logEntries.appendChild(el);
      });
      els.logEntries.scrollTop = els.logEntries.scrollHeight;
    }
  }

  // ── Reset ──
  async function resetAll() {
    await api("/api/readings/reset", { method: "POST" });
    resetCapture();
    els.chatMessages.innerHTML =
      '<div class="chat-welcome"><p>AI-powered visual triage assistant ready.</p><p class="chat-hint">Capture an image or type a question below.</p></div>';

    tempChart.data.labels = [];
    tempChart.data.datasets[0].data = [];
    tempChart.update("none");
    els.tempValue.textContent = "--";

    els.logEntries.innerHTML = '<div class="log-empty">No events yet</div>';
    addLogEntry("System: All readings reset");
  }

  // ── Status ──
  async function pollStatus() {
    const data = await api("/api/status");
    els.statusCam.classList.toggle("active", !!data.camera);
    els.statusVlm.classList.toggle("active", !!data.vlm);
    els.statusTemp.classList.toggle("active", !!data.temp_sensor);
  }

  // ── On-Screen Keyboard ──
  const KEYS = [
    ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"],
    ["q", "w", "e", "r", "t", "y", "u", "i", "o", "p"],
    ["a", "s", "d", "f", "g", "h", "j", "k", "l"],
    ["⇧", "z", "x", "c", "v", "b", "n", "m", "⌫"],
    ["Close", "?", ",", "Space", ".", "⏎"],
  ];

  function buildKeyboard() {
    els.keyboard.innerHTML = "";
    KEYS.forEach((row) => {
      const rowEl = document.createElement("div");
      rowEl.className = "kb-row";
      row.forEach((key) => {
        const btn = document.createElement("button");
        btn.className = "kb-key";
        btn.setAttribute("data-key", key);

        if (key === "Space") {
          btn.className += " extra-wide";
          btn.textContent = " ";
        } else if (key === "Close") {
          btn.className += " kb-close";
          btn.textContent = "Close";
        } else if (key === "⇧" || key === "⌫" || key === "⏎") {
          btn.className += " wide";
          btn.textContent = key;
        } else {
          btn.textContent = shiftActive ? key.toUpperCase() : key;
        }

        btn.addEventListener("pointerdown", (e) => {
          e.preventDefault();
          handleKey(key);
        });

        rowEl.appendChild(btn);
      });
      els.keyboard.appendChild(rowEl);
    });
  }

  function handleKey(key) {
    if (!keyboardTarget) return;

    if (key === "Close") {
      closeKeyboard();
      return;
    }
    if (key === "⇧") {
      shiftActive = !shiftActive;
      buildKeyboard();
      return;
    }
    if (key === "⌫") {
      keyboardTarget.value = keyboardTarget.value.slice(0, -1);
      return;
    }
    if (key === "⏎") {
      closeKeyboard();
      sendChatMessage();
      return;
    }
    if (key === "Space") {
      keyboardTarget.value += " ";
      return;
    }

    const char = shiftActive ? key.toUpperCase() : key;
    keyboardTarget.value += char;

    if (shiftActive) {
      shiftActive = false;
      buildKeyboard();
    }
  }

  function openKeyboard(inputEl) {
    keyboardTarget = inputEl;
    els.keyboardOverlay.classList.remove("hidden");
  }

  function closeKeyboard() {
    els.keyboardOverlay.classList.add("hidden");
    keyboardTarget = null;
  }

  // ── Event Binding ──
  function bindEvents() {
    els.btnCapture.addEventListener("click", captureFrame);
    els.btnUploadVlm.addEventListener("click", analyzeWithVlm);
    els.btnResetCapture.addEventListener("click", resetCapture);
    els.btnSend.addEventListener("click", sendChatMessage);
    els.btnResetAll.addEventListener("click", resetAll);

    els.chatInput.addEventListener("focus", (e) => {
      e.preventDefault();
      openKeyboard(els.chatInput);
    });

    els.chatInput.addEventListener("click", (e) => {
      e.preventDefault();
      openKeyboard(els.chatInput);
    });
  }

  // ── Init ──
  function init() {
    updateClock();
    setInterval(updateClock, 1000);

    buildKeyboard();
    initTempChart();
    bindEvents();

    addLogEntry("System: VI Triage UI loaded");

    pollStatus();
    setInterval(pollStatus, 10000);
    setInterval(pollTemperature, 3000);
    setInterval(pollSensorLog, 5000);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
