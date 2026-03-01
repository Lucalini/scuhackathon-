(function () {
  "use strict";

  function inFullscreen() {
    return !!document.fullscreenElement;
  }

  function updateIcon(btn) {
    var active = inFullscreen();
    document.documentElement.classList.toggle("is-fullscreen", active);
    if (document.body) {
      document.body.classList.toggle("is-fullscreen", active);
    }
    btn.textContent = active ? "🗗" : "⛶";
  }

  async function toggleFullscreen() {
    const root = document.documentElement;
    if (!inFullscreen()) {
      await root.requestFullscreen();
    } else {
      await document.exitFullscreen();
    }
  }

  function init() {
    var btn = document.getElementById("btn-fullscreen");
    if (!btn || !document.fullscreenEnabled) {
      if (btn) btn.classList.add("hidden");
      return;
    }

    updateIcon(btn);
    btn.addEventListener("click", function () {
      toggleFullscreen().catch(function () {});
    });
    document.addEventListener("fullscreenchange", function () {
      updateIcon(btn);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
