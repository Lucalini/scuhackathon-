(function () {
  "use strict";

  function updateClock() {
    var el = document.getElementById("clock");
    if (!el) return;
    var now = new Date();
    el.textContent = now.toLocaleTimeString("en-US", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });
  }

  function showToast(message, type) {
    var container = document.getElementById("toast-container");
    if (!container) return;
    var toast = document.createElement("div");
    toast.className = "toast toast-" + (type || "info");
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(function () { toast.remove(); }, 3000);
  }

  async function handleEscalate() {
    var btn = document.getElementById("btn-escalate-detail");
    if (!btn) return;
    var entryId = btn.dataset.entryId;
    if (!entryId) return;

    btn.disabled = true;
    try {
      var res = await fetch("/api/entries/" + entryId + "/escalate", { method: "POST" });
      if (res.ok) {
        btn.textContent = "Escalated";
        showToast("Entry escalated", "success");
      } else {
        var data = await res.json().catch(function () { return {}; });
        showToast(data.detail || "Escalate failed.", "error");
        btn.disabled = false;
      }
    } catch (e) {
      showToast("Escalate failed.", "error");
      btn.disabled = false;
    }
  }

  function init() {
    updateClock();
    setInterval(updateClock, 1000);

    var btn = document.getElementById("btn-escalate-detail");
    if (btn) {
      btn.addEventListener("click", handleEscalate);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
