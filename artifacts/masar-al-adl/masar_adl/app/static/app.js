/* مسار العدل — external behaviour only (CSP: no inline scripts / style attributes). */
(function () {
  "use strict";
  // Confirmation before sensitive actions (forms carrying data-confirm).
  document.addEventListener("submit", function (e) {
    var f = e.target;
    var m = f.getAttribute && f.getAttribute("data-confirm");
    if (m && !window.confirm(m)) { e.preventDefault(); return; }
    // Prevent accidental double submits on workflow forms.
    if (f.hasAttribute && f.hasAttribute("data-once")) {
      if (f.getAttribute("data-busy") === "1") { e.preventDefault(); return; }
      f.setAttribute("data-busy", "1");
    }
  });
  // Buttons that need their own confirmation (e.g. submit-to-court intent).
  document.addEventListener("click", function (e) {
    var b = e.target.closest && e.target.closest("[data-confirm-click]");
    if (b && !window.confirm(b.getAttribute("data-confirm-click"))) { e.preventDefault(); e.stopPropagation(); return; }
    var p = e.target.closest && e.target.closest("[data-print]");
    if (p) { e.preventDefault(); window.print(); }
  }, true);

  // Mobile navigation toggle.
  var btn = document.getElementById("menu-btn"), bar = document.getElementById("topbar");
  if (btn && bar) {
    btn.addEventListener("click", function () {
      var open = bar.classList.toggle("open");
      btn.setAttribute("aria-expanded", open ? "true" : "false");
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && bar.classList.contains("open")) { bar.classList.remove("open"); btn.setAttribute("aria-expanded", "false"); btn.focus(); }
    });
  }

  // Request type options driven by selected entity. Data comes from a data attribute (no inline script).
  var holder = document.getElementById("types-data");
  var ent = document.getElementById("entity_id"), typ = document.getElementById("request_type");
  if (holder && ent && typ) {
    var map = {};
    try { map = JSON.parse(holder.getAttribute("data-types") || holder.textContent || "{}"); } catch (err) { map = {}; }
    var fill = function () {
      typ.innerHTML = "";
      (map[ent.value] || []).forEach(function (t) {
        var o = document.createElement("option"); o.value = t[0]; o.textContent = t[1]; typ.appendChild(o);
      });
    };
    ent.addEventListener("change", fill); fill();
  }
})();
