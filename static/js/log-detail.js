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

    // clear previous rows (keep empty message node)
    Array.from(listEl.children).forEach(function (child) {
      if (child.id !== "log-list-empty") child.remove();
    });
    emptyEl.classList.remove("hidden");
    emptyEl.textContent = "Loading…";

    try {
      const res = await fetch("/api/entries?t=" + Date.now());
      const body = res.ok ? await res.json() : null;
      var entries = Array.isArray(body) ? body : (body && Array.isArray(body.entries) ? body.entries : (body && body.data ? body.data : []));
      if (!Array.isArray(entries)) entries = [];
      console.log("[Log] GET /api/entries status=" + res.status + " entriesCount=" + entries.length);

      if (!res.ok) {
        emptyEl.textContent = "Could not load entries. Tap Refresh to try again.";
        return;
      }
      if (entries.length === 0) {
        emptyEl.textContent = "No entries yet. Capture from the Triage screen.";
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
      emptyEl.textContent = "Could not load entries. Tap Refresh to try again.";
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

    const serverRendered = contentEl.getAttribute("data-server-rendered") === "true";
    if (serverRendered) {
      const btnEscalate = document.getElementById("btn-escalate");
      if (btnEscalate && !btnEscalate.disabled) {
        btnEscalate.onclick = () => escalateEntry(entryId);
      }
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

  // sort catalog by severity (tags): cycle asc -> desc -> original order
  function initLogCatalogSort() {
    const catalog = document.getElementById("log-catalog");
    const sortBtn = document.getElementById("log-sort-btn");
    if (!catalog || !sortBtn) return;
    const emptyEl = document.getElementById("log-catalog-empty");
    const items = Array.from(catalog.querySelectorAll(".log-catalog-item"));
    if (items.length === 0) return;

    let order = 0; // 0 = original, 1 = severity asc, 2 = severity desc
    const originalOrder = items.slice();
    sortBtn.title = "Sort by severity";

    sortBtn.addEventListener("click", function () {
      order = (order + 1) % 3;
      if (order === 0) {
        originalOrder.forEach(function (el) { catalog.appendChild(el); });
        sortBtn.title = "Sort by severity";
      } else {
        const sorted = items.slice().sort(function (a, b) {
          const sa = parseInt(a.getAttribute("data-severity"), 10);
          const sb = parseInt(b.getAttribute("data-severity"), 10);
          return order === 1 ? sa - sb : sb - sa;
        });
        sorted.forEach(function (el) { catalog.appendChild(el); });
        sortBtn.title = order === 1 ? "Sort: severity low→high (click again)" : "Sort: severity high→low (click again)";
      }
    });
  }

  // filter by category: severity, confidence, escalated only
  function applyLogCatalogFilters() {
    const catalog = document.getElementById("log-catalog");
    const severityVal = (document.getElementById("log-filter-severity") || {}).value || "";
    const confidenceVal = (document.getElementById("log-filter-confidence") || {}).value || "";
    const escalatedOnly = (document.getElementById("log-filter-escalated") || {}).checked || false;
    const emptyEl = document.getElementById("log-catalog-empty");
    const noMatchEl = document.getElementById("log-catalog-no-match");
    if (!catalog) return;
    const items = catalog.querySelectorAll(".log-catalog-item");
    let visibleCount = 0;
    items.forEach(function (el) {
      const sev = String(el.getAttribute("data-severity") || "");
      const confStr = el.getAttribute("data-confidence") || "";
      const conf = confStr === "" ? NaN : parseFloat(confStr, 10);
      const escalated = el.getAttribute("data-escalated") === "true";
      let show = true;
      if (severityVal !== "" && sev !== severityVal) show = false;
      if (show && confidenceVal !== "") {
        if (confidenceVal === "high" && (isNaN(conf) || conf < 80)) show = false;
        else if (confidenceVal === "medium" && (isNaN(conf) || conf < 50 || conf >= 80)) show = false;
        else if (confidenceVal === "low" && (isNaN(conf) || conf >= 50)) show = false;
      }
      if (show && escalatedOnly && !escalated) show = false;
      el.style.display = show ? "" : "none";
      if (show) visibleCount += 1;
    });
    if (emptyEl) emptyEl.classList.toggle("hidden", items.length > 0);
    if (noMatchEl) noMatchEl.classList.toggle("hidden", visibleCount > 0 || items.length === 0);
  }

  function initLogCatalogFilters() {
    const catalog = document.getElementById("log-catalog");
    const filtersBar = document.querySelector(".log-filters");
    if (!catalog) return;
    if (filtersBar) {
      filtersBar.addEventListener("change", function (e) {
        if (e.target.id === "log-filter-severity" || e.target.id === "log-filter-confidence" || e.target.id === "log-filter-escalated") {
          applyLogCatalogFilters();
        }
      });
    }
    applyLogCatalogFilters();
  }

  function init() {
    if (document.getElementById("log-list") || document.getElementById("log-catalog")) {
      window.refreshLogList = function () { window.location.reload(); };
      var refreshBtn = document.getElementById("log-refresh");
      if (refreshBtn) refreshBtn.addEventListener("click", function () { window.location.reload(); });
      initLogCatalogSort();
      initLogCatalogFilters();
    }
    if (document.getElementById("detail-content")) initDetailPage();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
