
(function () {
  "use strict";

  const $ = (sel) => document.querySelector(sel);

  // update clock in header
  function updateClock() {
    const el = document.getElementById("clock");
    if (!el) return;
    const now = new Date();
    el.textContent = now.toLocaleTimeString("en-US", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });
  }

  // show toast; type: success|warning|error|info (issue #15)
  function showToast(message, type) {
    const container = document.getElementById("toast-container");
    if (!container) return;
    const toast = document.createElement("div");
    toast.className = "toast toast-" + (type || "info");
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
  }

  // show loading overlay with optional text
  function showLoading(text) {
    const overlay = document.getElementById("loading-overlay");
    const textEl = document.getElementById("loading-text");
    if (overlay) overlay.classList.remove("hidden");
    if (textEl) textEl.textContent = text || "Processing...";
  }

  function hideLoading() {
    const overlay = document.getElementById("loading-overlay");
    if (overlay) overlay.classList.add("hidden");
  }

  // severity 0-3 to label (issue #15: NON-ISSUE, MINOR, MODERATE, SEVERE)
  function severityLabel(severity) {
    const labels = ["NON-ISSUE", "MINOR", "MODERATE", "SEVERE"];
    return labels[Number(severity)] ?? "—";
  }

  // post /api/capture, show result or toast on 501 (issue #15: disable capture, pulse, Analyzing wound...)
  async function handleCapture() {
    const btnCapture = document.getElementById("btn-capture");
    if (btnCapture) {
      btnCapture.disabled = true;
      btnCapture.classList.add("capture-pulsing");
    }
    showLoading("Analyzing wound...");
    try {
      const res = await fetch("/api/capture", { method: "POST" });
      const data = res.ok ? await res.json() : {};
      hideLoading();
      if (btnCapture) {
        btnCapture.disabled = false;
        btnCapture.classList.remove("capture-pulsing");
      }


      if (!res.ok) {
        if (res.status === 501 || (data.detail && String(data.detail).includes("Not implemented"))) {
          showToast("Capture not available yet (BE-6 pending).", "error");
        } else {
          showToast(data.detail || "Capture failed.", "error");
        }
        return;
      }

      const entry = data.entry ?? data;
      const id = entry.id;
      if (id == null) {
        showToast("Unexpected response from server.", "error");
        return;
      }

      window.__triageEntryId = id;
      window.__triageFollowUpCount = 0;

      const resultsEl = document.getElementById("triage-results");
      const followupSection = document.getElementById("followup-section");
      const badge = document.getElementById("result-severity-badge");
      const confidenceEl = document.getElementById("result-confidence");
      const reasoningEl = document.getElementById("result-reasoning");
      const barFill = document.getElementById("confidence-bar-fill");
      const bar = document.getElementById("confidence-bar");

      if (resultsEl) resultsEl.classList.remove("hidden");
      if (followupSection) followupSection.classList.remove("hidden");

      const severity = Number(entry.severity);
      const severityClass = severity >= 0 && severity <= 3 ? severity : 1;
      const badgeClass = "severity-badge severity-badge--large severity-" + severityClass;
      if (badge) {
        badge.className = badgeClass;
        badge.textContent = severityLabel(severity);
      }
      const confidence = entry.confidence != null ? Math.round(entry.confidence) : 0;
      if (confidenceEl) confidenceEl.textContent = confidence + "%";
      if (barFill) {
        barFill.style.width = confidence + "%";
        barFill.className = "confidence-bar-fill severity-" + severityClass;
      }
      if (bar) {
        bar.setAttribute("aria-valuenow", confidence);
      }
      if (reasoningEl) reasoningEl.textContent = entry.vlm_reasoning || "—";

      const followupChat = document.getElementById("followup-chat");
      const followupMessages = document.getElementById("followup-messages");
      if (followupChat) followupChat.classList.add("hidden");
      if (followupMessages) followupMessages.innerHTML = "";

      showToast("Triage complete", "success");
      if (confidence < 60) {
        showToast("Low confidence — consider escalating", "warning");
      }
    } catch (e) {
      hideLoading();
      if (btnCapture) {
        btnCapture.disabled = false;
        btnCapture.classList.remove("capture-pulsing");
      }
      console.error("Capture error:", e);
      showToast("Capture failed.", "error");
    }
  }

  async function pollTemperature() {
    const el = document.getElementById("temp-value");
    if (!el) return;
    try {
      const res = await fetch("/api/temperature");
      if (!res.ok) {
        el.textContent = "—";
        return;
      }
      const data = await res.json();
      const temp = data.temperature_c ?? data.temp_c;
      if (temp != null) el.textContent = Number(temp).toFixed(1);
      else el.textContent = "—";
    } catch (_) {
      el.textContent = "—";
    }
  }

  // post /api/entries/:id/chat, max 3 turns
  async function sendFollowUp() {
    const entryId = window.__triageEntryId;
    if (entryId == null) return;
    if ((window.__triageFollowUpCount || 0) >= 3) {
      showToast("Maximum 3 follow-up questions.", "error");
      return;
    }

    const input = document.getElementById("followup-input");
    const question = input?.value?.trim();
    if (!question) return;

    input.value = "";
    const messagesEl = document.getElementById("followup-messages");
    if (messagesEl) {
      const userMsg = document.createElement("div");
      userMsg.className = "chat-msg user";
      userMsg.textContent = question;
      messagesEl.appendChild(userMsg);
    }

    showLoading("Thinking...");
    try {
      const res = await fetch("/api/entries/" + entryId + "/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: question }),
      });
      const data = res.ok ? await res.json() : {};
      hideLoading();

      if (!res.ok) {
        if (res.status === 501) showToast("Follow-up not available yet (BE-6 pending).", "error");
        else showToast(data.detail || "Failed.", "error");
        return;
      }

      window.__triageFollowUpCount = (window.__triageFollowUpCount || 0) + 1;
      const answer = data.answer ?? data.response ?? data.message ?? "—";
      if (messagesEl) {
        const assistantMsg = document.createElement("div");
        assistantMsg.className = "chat-msg assistant";
        assistantMsg.textContent = answer;
        messagesEl.appendChild(assistantMsg);
      }
    } catch (e) {
      hideLoading();
      showToast("Request failed.", "error");
    }
  }

  // post /api/entries/:id/escalate
  async function handleEscalate() {
    const entryId = window.__triageEntryId;
    if (entryId == null) {
      showToast("Capture first, then escalate.", "error");
      return;
    }
    try {
      const res = await fetch("/api/entries/" + entryId + "/escalate", { method: "POST" });
      if (res.ok) {
        showToast("Entry escalated", "success");
        const btn = document.getElementById("btn-escalate");
        if (btn) { btn.textContent = "Escalated"; btn.disabled = true; }
      } else {
        const data = await res.json().catch(() => ({}));
        showToast(data.detail || "Escalate failed.", "error");
      }
    } catch (e) {
      showToast("Escalate failed.", "error");
    }
  }

  // reset triage ui state
  function handleNewPatient() {
    window.__triageEntryId = null;
    window.__triageFollowUpCount = 0;

    const resultsEl = document.getElementById("triage-results");
    const followupSection = document.getElementById("followup-section");
    const followupChat = document.getElementById("followup-chat");
    const followupMessages = document.getElementById("followup-messages");
    const followupInput = document.getElementById("followup-input");
    const btnEscalate = document.getElementById("btn-escalate");

    if (resultsEl) resultsEl.classList.add("hidden");
    if (followupSection) followupSection.classList.add("hidden");
    if (followupChat) followupChat.classList.add("hidden");
    if (followupMessages) followupMessages.innerHTML = "";
    if (followupInput) followupInput.value = "";
    if (btnEscalate) { btnEscalate.textContent = "ESCALATE"; btnEscalate.disabled = false; }
  }

  function toggleFollowUp() {
    const chat = document.getElementById("followup-chat");
    if (chat) chat.classList.toggle("hidden");
  }

  // bind triage only on triage page, start temp poll
  function init() {
    updateClock();
    setInterval(updateClock, 1000);

    if (document.getElementById("log-list") || document.getElementById("detail-content")) {
      return;
    }

    const btnCapture = document.getElementById("btn-capture");
    if (!btnCapture) return;

    btnCapture.addEventListener("click", handleCapture);
    document.getElementById("btn-escalate")?.addEventListener("click", handleEscalate);
    document.getElementById("btn-new-patient")?.addEventListener("click", handleNewPatient);
    document.getElementById("btn-toggle-followup")?.addEventListener("click", toggleFollowUp);
    document.getElementById("btn-followup-send")?.addEventListener("click", sendFollowUp);
    document.getElementById("followup-input")?.addEventListener("keydown", (e) => {
      if (e.key === "Enter") sendFollowUp();
    });

    pollTemperature();
    setInterval(pollTemperature, 2000);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
