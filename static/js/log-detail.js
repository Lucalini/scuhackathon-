// patient log and entry detail
(function () {
  "use strict";

  const $ = (sel) => document.querySelector(sel);

  function formatRelativeTime(isoStr) {
    if (!isoStr) return "—";
    const d = new Date(isoStr);
    const now = new Date();
    const sec = Math.floor((now - d) / 1000);
    if (sec < 60) return "Just now";
    if (sec < 3600) return Math.floor(sec / 60) + " min ago";
    if (sec < 86400) return Math.floor(sec / 3600) + " h ago";
    return d.toLocaleDateString() + " " + d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }

  function severityLabel(severity) {
    const labels = ["NON-ISSUE", "MINOR", "MODERATE", "SEVERE"];
    return labels[Number(severity)] || "—";
  }

  // log page list entries
  async function initLogPage() {
    const listEl = document.getElementById("log-list");
    const emptyEl = document.getElementById("log-list-empty");
    if (!listEl || !emptyEl) return;

    try {
      const res = await fetch("/api/entries");
      const entries = res.ok ? await res.json() : [];
      if (!Array.isArray(entries)) {
        emptyEl.textContent = "No entries yet. Capture from the Triage screen.";
        emptyEl.classList.remove("hidden");
        return;
      }
      if (entries.length === 0) {
        emptyEl.classList.remove("hidden");
        return;
      }
      emptyEl.classList.add("hidden");
      entries.forEach((entry) => {
        const row = document.createElement("a");
        row.href = "/log/" + entry.id;
        row.className = "log-list-item";
        const severity = Number(entry.severity);
        const badgeClass = "severity-badge severity-badge--small severity-" + (severity >= 0 && severity <= 3 ? severity : 1);
        row.innerHTML =
          '<span class="log-time">' +
          formatRelativeTime(entry.timestamp || entry.created_at) +
          "</span>" +
          '<span class="log-patient">' +
          (entry.patient_id || "Patient #" + entry.id) +
          "</span>" +
          '<span class="log-meta">' +
          '<span class="' +
          badgeClass +
          '">' +
          severityLabel(severity) +
          "</span>" +
          '<span class="log-confidence">' +
          (entry.confidence != null ? Math.round(entry.confidence) + "%" : "—") +
          "</span>" +
          (entry.escalated ? " ⚠️" : "") +
          (entry.synced ? " ☁️" : "") +
          "</span>";
        listEl.appendChild(row);
      });
    } catch (e) {
      console.error("Log page fetch error:", e);
      emptyEl.textContent = "No entries yet. Capture from the Triage screen.";
      emptyEl.classList.remove("hidden");
    }
  }

  // detail page single entry
  async function initDetailPage() {
    const contentEl = document.getElementById("detail-content");
    const loadingEl = document.getElementById("detail-loading");
    const notFoundEl = document.getElementById("detail-not-found");
    const idEl = document.getElementById("detail-id");
    if (!contentEl || !idEl) return;

    const entryId = idEl.textContent.trim();
    if (!entryId) {
      if (loadingEl) loadingEl.classList.add("hidden");
      if (notFoundEl) notFoundEl.classList.remove("hidden");
      return;
    }

    try {
      const res = await fetch("/api/entries/" + entryId);
      if (!res.ok) {
        contentEl.classList.add("hidden");
        if (loadingEl) loadingEl.classList.add("hidden");
        if (notFoundEl) notFoundEl.classList.remove("hidden");
        return;
      }
      const entry = await res.json();
      if (loadingEl) loadingEl.classList.add("hidden");
      if (notFoundEl) notFoundEl.classList.add("hidden");

      const imgEl = document.getElementById("detail-image");
      const imgPlaceholder = document.getElementById("detail-image-placeholder");
      if (entry.image_filename && imgEl) {
        imgEl.src = "/api/captures/" + encodeURIComponent(entry.image_filename);
        imgEl.classList.remove("hidden");
        if (imgPlaceholder) imgPlaceholder.classList.add("hidden");
      }

      const set = (id, text) => {
        const el = document.getElementById(id);
        if (el) el.textContent = text != null ? text : "—";
      };
      set("detail-time", formatRelativeTime(entry.timestamp || entry.created_at));
      set("detail-patient", entry.patient_id || "Patient #" + entry.id);
      set("detail-temp", entry.temperature_c != null ? entry.temperature_c + " °C" : "—");
      set("detail-severity", severityLabel(entry.severity));
      set("detail-confidence", entry.confidence != null ? Math.round(entry.confidence) + "%" : "—");
      set("detail-reasoning", entry.vlm_reasoning || "—");

      const chatEl = document.getElementById("detail-chat");
      if (chatEl) {
        if (entry.chat_history) {
          try {
            const chat = typeof entry.chat_history === "string" ? JSON.parse(entry.chat_history) : entry.chat_history;
            chatEl.innerHTML = Array.isArray(chat)
              ? chat.map((c) => '<div class="chat-msg user">' + (c.q || c.question) + "</div><div class="chat-msg assistant">" + (c.a || c.answer) + "</div>").join("")
              : "—";
          } catch (_) {
            chatEl.textContent = entry.chat_history;
          }
        } else {
          chatEl.textContent = "—";
        }
      }

      const guidanceEl = document.getElementById("detail-guidance");
      if (guidanceEl) {
        guidanceEl.textContent = entry.remote_guidance || "No remote guidance yet.";
      }

      const btnEscalate = document.getElementById("btn-escalate");
      if (btnEscalate) {
        if (entry.escalated) {
          btnEscalate.textContent = "Escalated";
          btnEscalate.disabled = true;
        } else {
          btnEscalate.onclick = () => escalateEntry(entryId);
        }
      }
    } catch (e) {
      console.error("Detail page fetch error:", e);
      if (loadingEl) loadingEl.classList.add("hidden");
      if (contentEl) contentEl.classList.add("hidden");
      if (notFoundEl) notFoundEl.classList.remove("hidden");
    }
  }

  async function escalateEntry(entryId) {
    try {
      const res = await fetch("/api/entries/" + entryId + "/escalate", { method: "POST" });
      if (res.ok) {
        const btn = document.getElementById("btn-escalate");
        if (btn) {
          btn.textContent = "Escalated";
          btn.disabled = true;
        }
      }
    } catch (e) {
      console.error("Escalate error:", e);
    }
  }

  function init() {
    if (document.getElementById("log-list")) initLogPage();
    if (document.getElementById("detail-content")) initDetailPage();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
