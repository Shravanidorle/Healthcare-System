/* ============================================================
   ui.js — Drawer, settings, clock/timer, misc UI helpers
   ============================================================ */

// ── DRAWER ──────────────────────────────────────────────────

function toggleDrawer() {
  const isOpen = document.getElementById("drawer").classList.contains("open");
  ["drawer", "drw-overlay", "hamburger"].forEach((id) =>
    document.getElementById(id).classList.toggle("open", !isOpen),
  );
}

function closeDrawer() {
  ["drawer", "drw-overlay", "hamburger"].forEach((id) =>
    document.getElementById(id).classList.remove("open"),
  );
}

function goAlerts() {
  closeDrawer();
  setTimeout(
    () =>
      document
        .getElementById("alert-log-card")
        .scrollIntoView({ behavior: "smooth" }),
    300,
  );
}

function goSettings() {
  document
    .getElementById("settings-sec")
    .scrollIntoView({ behavior: "smooth", block: "nearest" });
}

// ── SETTINGS TOGGLES ────────────────────────────────────────

function toggleSetting(el) {
  el.classList.toggle("on");
}

function togglePrivacy(el) {
  el.classList.toggle("on");
  document.getElementById("video-feed").style.filter = el.classList.contains(
    "on",
  )
    ? "blur(14px) brightness(0.22)"
    : "";
}

// ── CLOCK ───────────────────────────────────────────────────

function updateClock() {
  document.getElementById("clock").textContent = new Date().toLocaleTimeString(
    "en-GB",
  );
}
setInterval(updateClock, 1000);
updateClock();

// ── SESSION TIMER ───────────────────────────────────────────

const sesStart = Date.now();

function updateTimer() {
  const e = Math.floor((Date.now() - sesStart) / 1000);
  const mm = String(Math.floor(e / 60)).padStart(2, "0");
  const ss = String(e % 60).padStart(2, "0");
  document.getElementById("sess-time").textContent = `${mm}:${ss}`;

  const hh = String(Math.floor(e / 3600)).padStart(2, "0");
  const mm2 = String(Math.floor((e % 3600) / 60)).padStart(2, "0");
  const ss2 = String(e % 60).padStart(2, "0");
  document.getElementById("foot-uptime").textContent =
    `UPTIME: ${hh}:${mm2}:${ss2}`;
}
setInterval(updateTimer, 1000);

// ── CAMERA OFFLINE ───────────────────────────────────────────

function showOff(id) {
  const el = document.getElementById(id);
  if (el) el.style.display = "flex";
}
