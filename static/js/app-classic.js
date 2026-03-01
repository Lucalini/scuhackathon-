/* classic triage UI */

(function () {
  "use strict";

  let capturedImage = null;
  let tempChart = null;
  let keyboardTarget = null;
  let shiftActive = false;

  const $ = (sel) => document.querySelector(sel);
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

  function updateClock() {
    if (!els.clock) return;
    const now = new Date();
    els.clock.textContent = now.toLocaleTimeString("en-US", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });
  }

  function showLoading(text) {
    if (els.loadingText) els.loadingText.textContent = text || "Processing...";
    if (els.loadingOverlay) els.loadingOverlay.classList.remove("hidden");
  }

  function hideLoading() {
    if (els.loadingOverlay) els.loadingOverlay.classList.add("hidden");
  }

  async function api(endpoint, options = {}) {
    try {
      const res = await fetch(endpoint, {
        headers: { "Content-Type": "application/json" },
        ...options,
      });
      return await res.json();
    } catch (e) {
      console.error("API error [" + endpoint + "]:", e);
      return { status: "error", message: e.message };
    }
  }

  async function captureFrame() {
    showLoading("Capturing...");
    const data = await api("/api/camera/capture", { method: "POST" });
    hideLoading();
    if (data.status === "ok" && data.image && els.cameraPreview && els.cameraPlaceholder) {
      capturedImage = data.image;
      els.cameraPreview.src = "data:image/jpeg;base64," + data.image;
      els.cameraPreview.classList.remove("hidden");
      els.cameraPlaceholder.classList.add("hidden");
      addLogEntry("Camera: Frame captured");
    } else {
      addLogEntry("Camera: " + (data.message || "Capture failed"));
    }
  }

  function resetCapture() {
    capturedImage = null;
    if (els.cameraPreview) {
      els.cameraPreview.classList.add("hidden");
      els.cameraPreview.src = "";
    }
    if (els.cameraPlaceholder) els.cameraPlaceholder.classList.remove("hidden");
    addLogEntry("Camera: Preview reset");
  }

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
    if (!els.chatInput) return;
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
    if (!els.chatMessages) return;
    const welcome = els.chatMessages.querySelector(".chat-welcome");
    if (welcome) welcome.remove();
    const msg = document.createElement("div");
    msg.className = "chat-msg " + role;
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

  function initTempChart() {
    if (!els.tempChart || typeof Chart === "undefined") return;
    const ctx = els.tempChart.getContext("2d");
    tempChart = new Chart(ctx, {
      type: "line",
      data: {
        labels: [],
        datasets: [{
          label: "°C",
          data: [],
          borderColor: "#4fc3f7",
          backgroundColor: "rgba(79,195,247,0.08)",
          borderWidth: 1.5,
          pointRadius: 0,
          tension: 0.3,
          fill: true,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 300 },
        plugins: { legend: { display: false } },
        scales: {
          x: {
            display: true,
            ticks: { color: "#8b8fa3", font: { size: 8 }, maxTicksLimit: 6, maxRotation: 0 },
            grid: { color: "rgba(46,51,72,0.5)" },
          },
          y: {
            display: true,
            ticks: { color: "#8b8fa3", font: { size: 9 }, maxTicksLimit: 5 },
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
    const val = data.temp_c != null ? data.temp_c : data.temperature_c;
    if (val != null && els.tempValue && tempChart) {
      els.tempValue.textContent = Number(val).toFixed(1);
      const time = data.time || new Date().toLocaleTimeString("en-US", { hour12: false });
      tempChart.data.labels.push(time);
      tempChart.data.datasets[0].data.push(Number(val));
      if (tempChart.data.labels.length > 30) {
        tempChart.data.labels.shift();
        tempChart.data.datasets[0].data.shift();
      }
      tempChart.update("none");
    }
  }

  function addLogEntry(message) {
    if (!els.logEntries) return;
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
    if (Array.isArray(data) && data.length > 0 && els.logEntries) {
      els.logEntries.innerHTML = "";
      data.forEach(function (entry) {
        const el = document.createElement("div");
        el.className = "log-entry";
        el.innerHTML = "<span class=\"log-time\">" + (entry.time || "") + "</span><span class=\"log-msg\">" + (entry.message || "") + "</span>";
        els.logEntries.appendChild(el);
      });
      els.logEntries.scrollTop = els.logEntries.scrollHeight;
    }
  }

  async function resetAll() {
    await api("/api/readings/reset", { method: "POST" });
    resetCapture();
    if (els.chatMessages) {
      els.chatMessages.innerHTML = "<div class=\"chat-welcome\"><p>AI-powered visual triage assistant ready.</p><p class=\"chat-hint\">Capture an image or type a question below.</p></div>";
    }
    if (tempChart) {
      tempChart.data.labels = [];
      tempChart.data.datasets[0].data = [];
      tempChart.update("none");
    }
    if (els.tempValue) els.tempValue.textContent = "--";
    if (els.logEntries) {
      els.logEntries.innerHTML = "<div class=\"log-empty\">No events yet</div>";
      addLogEntry("System: All readings reset");
    }
  }

  async function pollStatus() {
    const data = await api("/api/status");
    if (els.statusCam) els.statusCam.classList.toggle("active", !!data.camera);
    if (els.statusVlm) els.statusVlm.classList.toggle("active", !!data.vlm);
    if (els.statusTemp) els.statusTemp.classList.toggle("active", !!data.temp_sensor);
  }

  var KEYS = [
    ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"],
    ["q", "w", "e", "r", "t", "y", "u", "i", "o", "p"],
    ["a", "s", "d", "f", "g", "h", "j", "k", "l"],
    ["\u21E7", "z", "x", "c", "v", "b", "n", "m", "\u232B"],
    ["Close", "?", ",", "Space", ".", "\u23CE"],
  ];

  function buildKeyboard() {
    if (!els.keyboard) return;
    els.keyboard.innerHTML = "";
    KEYS.forEach(function (row) {
      const rowEl = document.createElement("div");
      rowEl.className = "kb-row";
      row.forEach(function (key) {
        const btn = document.createElement("button");
        btn.className = "kb-key";
        btn.setAttribute("data-key", key);
        if (key === "Space") {
          btn.className += " extra-wide";
          btn.textContent = " ";
        } else if (key === "Close") {
          btn.className += " kb-close";
          btn.textContent = "Close";
        } else if (key === "\u21E7" || key === "\u232B" || key === "\u23CE") {
          btn.className += " wide";
          btn.textContent = key;
        } else {
          btn.textContent = shiftActive ? key.toUpperCase() : key;
        }
        btn.addEventListener("pointerdown", function (e) {
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
    if (key === "\u21E7") {
      shiftActive = !shiftActive;
      buildKeyboard();
      return;
    }
    if (key === "\u232B") {
      keyboardTarget.value = keyboardTarget.value.slice(0, -1);
      return;
    }
    if (key === "\u23CE") {
      closeKeyboard();
      sendChatMessage();
      return;
    }
    if (key === "Space") {
      keyboardTarget.value += " ";
      return;
    }
    var char = shiftActive ? key.toUpperCase() : key;
    keyboardTarget.value += char;
    if (shiftActive) {
      shiftActive = false;
      buildKeyboard();
    }
  }

  function openKeyboard(inputEl) {
    keyboardTarget = inputEl;
    if (els.keyboardOverlay) els.keyboardOverlay.classList.remove("hidden");
  }

  function closeKeyboard() {
    if (els.keyboardOverlay) els.keyboardOverlay.classList.add("hidden");
    keyboardTarget = null;
  }

  function bindEvents() {
    if (els.btnCapture) els.btnCapture.addEventListener("click", captureFrame);
    if (els.btnUploadVlm) els.btnUploadVlm.addEventListener("click", analyzeWithVlm);
    if (els.btnResetCapture) els.btnResetCapture.addEventListener("click", resetCapture);
    if (els.btnSend) els.btnSend.addEventListener("click", sendChatMessage);
    if (els.btnResetAll) els.btnResetAll.addEventListener("click", resetAll);
    if (els.chatInput) {
      els.chatInput.addEventListener("focus", function (e) {
        e.preventDefault();
        openKeyboard(els.chatInput);
      });
      els.chatInput.addEventListener("click", function (e) {
        e.preventDefault();
        openKeyboard(els.chatInput);
      });
    }
  }

  function init() {
    updateClock();
    setInterval(updateClock, 1000);
    buildKeyboard();
    initTempChart();
    bindEvents();
    addLogEntry("System: VI Triage (classic) loaded");
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
