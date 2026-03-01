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

  function sortCards(criterion) {
    var grid = document.getElementById("log-grid");
    if (!grid) return;
    var cards = Array.from(grid.querySelectorAll(".patient-card"));
    if (cards.length === 0) return;

    cards.sort(function (a, b) {
      switch (criterion) {
        case "severity":
          return (Number(b.dataset.severity) || 0) - (Number(a.dataset.severity) || 0);
        case "confidence":
          return (Number(b.dataset.confidence) || 0) - (Number(a.dataset.confidence) || 0);
        case "escalated":
          return (Number(b.dataset.escalated) || 0) - (Number(a.dataset.escalated) || 0);
        default:
          return (b.dataset.time || "").localeCompare(a.dataset.time || "");
      }
    });

    cards.forEach(function (card) {
      grid.appendChild(card);
    });
  }

  function init() {
    updateClock();
    setInterval(updateClock, 1000);

    var sortSelect = document.getElementById("sort-select");
    if (sortSelect) {
      sortSelect.addEventListener("change", function () {
        sortCards(this.value);
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
