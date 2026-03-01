// triage page: classic layout + capture / follow-up / escalate
(function () {
  "use strict";

  let tempChart = null;
  let currentEntryId = null;
  let followUpCount = 0;
  const MAX_FOLLOWUPS = 3;

  const $ = (sel) => document.querySelector(sel);
  const els = {
    clock: $("#clock"),
    cameraViewport: $("#camera-viewport"),
    cameraStream: $("#camera-stream"),
    cameraPlaceholder: $("#camera-placeholder"),
    cameraPreview: $("#camera-preview"),
    btnCapture: $("#btn-capture"),
    btnReset: $("#btn-reset-capture"),
    chatMessages: $("#chat-messages"),
    chatInput: $("#chat-input"),
    btnSend: $("#btn-send"),
    btnEscalate: $("#btn-escalate"),
    tempValue: $("#temp-value"),
    tempChart: $("#temp-chart"),
    logEntries: $("#log-entries"),
    loadingOverlay: $("#loading-overlay"),
    loadingText: $("#loading-text"),
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

  function showToast(message, type) {
    const container = document.getElementById("toast-container");
    if (!container) return;
    const toast = document.createElement("div");
    toast.className = "toast toast-" + (type || "info");
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
  }

  function showLoading(text) {
    if (els.loadingText) els.loadingText.textContent = text || "Processing...";
    if (els.loadingOverlay) els.loadingOverlay.classList.remove("hidden");
  }

  function hideLoading() {
    if (els.loadingOverlay) els.loadingOverlay.classList.add("hidden");
  }

  function severityLabel(severity) {
    const labels = ["NON-ISSUE", "MINOR", "MODERATE", "SEVERE"];
    return labels[Number(severity)] ?? "—";
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

  function clearChatToWelcome() {
    if (!els.chatMessages) return;
    els.chatMessages.innerHTML =
      '<div class="chat-welcome">' +
      '<p>AI-powered visual triage assistant ready.</p>' +
      '<p class="chat-hint">Tap Capture to take a photo and get severity assessment.</p>' +
      "</div>";
  }

  function showTriageResults(entry) {
    if (!els.chatMessages) return;
    const welcome = els.chatMessages.querySelector(".chat-welcome");
    if (welcome) welcome.remove();
    const severity = Number(entry.severity);
    const severityClass = severity >= 0 && severity <= 3 ? severity : 1;
    const confidence = entry.confidence != null ? Math.round(entry.confidence) : 0;
    const reasoning = entry.vlm_reasoning || "—";
    const block = document.createElement("div");
    block.className = "chat-triage-results";
    block.innerHTML =
      '<div class="triage-result-severity">' +
      '<span class="severity-badge severity-badge--large severity-' + severityClass + '">' + severityLabel(severity) + "</span>" +
      '<span class="result-confidence">' + confidence + "%</span>" +
      "</div>" +
      '<p class="triage-reasoning">' + reasoning + "</p>";
    els.chatMessages.appendChild(block);
    els.chatMessages.scrollTop = els.chatMessages.scrollHeight;
  }

  function appendChatMessage(role, content) {
    if (!els.chatMessages) return;
    const msg = document.createElement("div");
    msg.className = "chat-msg " + role;
    const textEl = document.createElement("div");
    textEl.textContent = content;
    msg.appendChild(textEl);
    els.chatMessages.appendChild(msg);
    els.chatMessages.scrollTop = els.chatMessages.scrollHeight;
  }

  async function handleCapture() {
    if (els.btnCapture) {
      els.btnCapture.disabled = true;
      els.btnCapture.classList.add("capture-pulsing");
    }
    showLoading("Analyzing wound...");
    try {
      const res = await fetch("/api/capture", { method: "POST" });
      const data = res.ok ? await res.json() : {};
      hideLoading();
      if (els.btnCapture) {
        els.btnCapture.disabled = false;
        els.btnCapture.classList.remove("capture-pulsing");
      }
      if (!res.ok) {
        showToast(data.detail || "Capture failed.", "error");
        return;
      }
      const entry = data.entry ?? data;
      const id = entry.id;
      if (id == null) {
        showToast("Unexpected response from server.", "error");
        return;
      }
      currentEntryId = id;
      followUpCount = 0;
      if (entry.image_filename && els.cameraPreview && els.cameraStream) {
        els.cameraPreview.src = "/api/captures/" + encodeURIComponent(entry.image_filename);
        els.cameraPreview.classList.remove("hidden");
        els.cameraStream.classList.add("hidden");
      }
      clearChatToWelcome();
      showTriageResults(entry);
      if (els.btnEscalate) {
        els.btnEscalate.disabled = false;
        els.btnEscalate.textContent = "Escalate";
      }
      addLogEntry("Capture: triage complete");
      showToast("Triage complete", "success");
      if ((entry.confidence != null ? entry.confidence : 100) < 60) {
        showToast("Low confidence — consider escalating", "warning");
      }
    } catch (e) {
      hideLoading();
      if (els.btnCapture) {
        els.btnCapture.disabled = false;
        els.btnCapture.classList.remove("capture-pulsing");
      }
      console.error("Capture error:", e);
      showToast("Capture failed.", "error");
    }
  }

  function handleReset() {
    currentEntryId = null;
    followUpCount = 0;
    if (els.cameraPreview && els.cameraStream) {
      els.cameraPreview.classList.add("hidden");
      els.cameraPreview.src = "";
      els.cameraStream.classList.remove("hidden");
    }
    clearChatToWelcome();
    if (els.btnEscalate) {
      els.btnEscalate.disabled = true;
      els.btnEscalate.textContent = "Escalate";
    }
    addLogEntry("New patient");
  }

  async function sendFollowUp() {
    if (currentEntryId == null) return;
    if (followUpCount >= MAX_FOLLOWUPS) {
      showToast("Maximum " + MAX_FOLLOWUPS + " follow-up questions.", "error");
      return;
    }
    const question = els.chatInput ? els.chatInput.value.trim() : "";
    if (!question) return;
    if (els.chatInput) els.chatInput.value = "";
    appendChatMessage("user", question);
    showLoading("Thinking...");
    try {
      const res = await fetch("/api/entries/" + currentEntryId + "/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: question }),
      });
      const data = res.ok ? await res.json() : {};
      hideLoading();
      if (!res.ok) {
        showToast(data.detail || "Failed.", "error");
        return;
      }
      followUpCount += 1;
      const answer = data.answer ?? data.response ?? data.message ?? "—";
      appendChatMessage("assistant", answer);
    } catch (e) {
      hideLoading();
      showToast("Request failed.", "error");
    }
  }

  async function handleEscalate() {
    if (currentEntryId == null) {
      showToast("Capture first, then escalate.", "error");
      return;
    }
    try {
      const res = await fetch("/api/entries/" + currentEntryId + "/escalate", { method: "POST" });
      if (res.ok) {
        showToast("Entry escalated", "success");
        if (els.btnEscalate) {
          els.btnEscalate.textContent = "Escalated";
          els.btnEscalate.disabled = true;
        }
        addLogEntry("Entry escalated");
      } else {
        const data = await res.json().catch(() => ({}));
        showToast(data.detail || "Escalate failed.", "error");
      }
    } catch (e) {
      showToast("Escalate failed.", "error");
    }
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
    try {
      const res = await fetch("/api/temperature");
      if (!res.ok) return;
      const data = await res.json();
      const val = data.temperature_c ?? data.temp_c;
      if (val != null && els.tempValue) {
        els.tempValue.textContent = Number(val).toFixed(1);
      }
      if (val != null && tempChart) {
        const time = data.timestamp ? new Date(data.timestamp).toLocaleTimeString("en-US", { hour12: false }) : new Date().toLocaleTimeString("en-US", { hour12: false });
        tempChart.data.labels.push(time);
        tempChart.data.datasets[0].data.push(Number(val));
        if (tempChart.data.labels.length > 30) {
          tempChart.data.labels.shift();
          tempChart.data.datasets[0].data.shift();
        }
        tempChart.update("none");
      }
    } catch (_) {}
  }

  function bindEvents() {
    if (els.btnCapture) els.btnCapture.addEventListener("click", handleCapture);
    if (els.btnReset) els.btnReset.addEventListener("click", handleReset);
    if (els.btnSend) els.btnSend.addEventListener("click", sendFollowUp);
    if (els.btnEscalate) els.btnEscalate.addEventListener("click", handleEscalate);
    if (els.chatInput) {
      els.chatInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") sendFollowUp();
      });
    }
  }

  function init() {
    updateClock();
    setInterval(updateClock, 1000);
    initTempChart();
    bindEvents();
    addLogEntry("Triage loaded");
    pollTemperature();
    setInterval(pollTemperature, 2000);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
