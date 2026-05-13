/* ============================================================
   socket.js — SocketIO events, alert handling, beep, /status
   ============================================================ */

var socket;

socket = io({
  reconnection: true,
  reconnectionDelay: 1000,
  reconnectionAttempts: Infinity
});

var fallCt = 0;
var alertCt = 0;

// ── CONNECTION ──────────────────────────────────────────────

socket.on("connect", () => {
  document.getElementById("live-dot").classList.add("on");
  const liveTxt = document.getElementById("live-txt");
  if (liveTxt) {
    liveTxt.textContent = "LIVE";
    liveTxt.style.color = "";
  }
  document.getElementById("sock-st").textContent = "ONLINE";
  document.getElementById("sock-st").className = "sbadge ok";
  showToast("success", "🔗 Connected", "Live socket connection established.");

  // Re-join the correct room upon successful connection/reconnection
  if (typeof curRoom !== 'undefined') {
    socket.emit('set_room', {room: curRoom});
    console.log(`[Socket] Re-joined room: ${curRoom} at ${new Date().toISOString()}`);
  }
});

socket.on("disconnect", () => {
  document.getElementById("live-dot").classList.remove("on");
  const liveTxt = document.getElementById("live-txt");
  if (liveTxt) {
    liveTxt.textContent = "Offline (Attempting Reconnect...)";
    liveTxt.style.color = "red";
  }
  document.getElementById("sock-st").textContent = "OFFLINE";
  document.getElementById("sock-st").className = "sbadge err";
  showToast("error", "⚡ Disconnected", "Socket lost. Reconnecting...");
});

socket.on("reconnect_attempt", () => {
  console.log(`[Socket] Reconnect attempt at ${new Date().toISOString()}`);
});

socket.on("connect_error", (error) => {
  console.error(`[Socket Error] at ${new Date().toISOString()}:`, error);
});

// ── FALL ALERT ──────────────────────────────────────────────

socket.on("alert", (data) => {
  fallCt++;
  alertCt++;

  const conf = data.confidence || 0;
  const confStr = conf + "%";
  const room = ROOMS.find((r) => r.id === curRoom);

  // Update stats
  document.getElementById("fall-ct").textContent = fallCt;
  document.getElementById("alert-ct").textContent = alertCt;
  document.getElementById("last-conf").textContent = confStr;
  document.getElementById("drw-badge").textContent = alertCt;

  // Confidence bar
  const cb = document.getElementById("cbar");
  cb.style.width = conf + "%";
  cb.className = "cbar-fill" + (conf >= 85 ? " danger" : "");
  document.getElementById("conf-pct").textContent = confStr;

  // Sparkline
  pushSpark(conf);

  // Alert banner
  document.getElementById("alert-conf").textContent =
    `Confidence: ${confStr} · ${room?.name || ""}`;
  document.getElementById("alert-banner").style.display = "block";

  // Toast
  showToast(
    "error",
    "🚨 FALL DETECTED",
    `${room?.name || "Camera"} · ${room?.patient || "Unknown"} · ${confStr}`,
    6000,
  );

  // Beep, log entries, export history
  playBeep();
  addLog(data.msg, confStr);
  addHist(confStr);
  alertHist.push({
    time: new Date().toLocaleString(),
    room: room?.name || curRoom,
    patient: room?.patient || "N/A",
    msg: data.msg || "Fall detected",
    conf,
  });

  // Auto-dismiss banner
  if (document.getElementById("tgl-auto").classList.contains("on")) {
    setTimeout(() => {
      document.getElementById("alert-banner").style.display = "none";
    }, 4000);
  }
});

// ── LOG HELPERS ─────────────────────────────────────────────

function addLog(msg, conf) {
  const log = document.getElementById("alert-log");
  const ph = document.getElementById("no-alerts-msg");
  if (ph) ph.remove();

  const li = document.createElement("li");
  li.innerHTML = `<div class="t">${new Date().toLocaleTimeString()}</div>⚠️ ${msg} <span class="c">(${conf})</span>`;
  log.insertBefore(li, log.firstChild);
  while (log.children.length > 20) log.removeChild(log.lastChild);
}

function addHist(conf) {
  const h = document.getElementById("drw-hist");
  const ph = document.getElementById("drw-no-alerts");
  if (ph) ph.remove();

  const room = ROOMS.find((r) => r.id === curRoom);
  const div = document.createElement("div");
  div.className = "hist-item";
  div.innerHTML = `<div class="ht">${new Date().toLocaleTimeString()} · ${room?.name || ""}</div>Fall detected <span class="hc">${conf}</span>`;
  h.insertBefore(div, h.firstChild);
  while (h.children.length > 30) h.removeChild(h.lastChild);
}

// ── BEEP ────────────────────────────────────────────────────

function playBeep() {
  if (!document.getElementById("tgl-sound").classList.contains("on")) return;
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    [880, 1100, 880].forEach((freq, i) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.type = "square";
      osc.frequency.setValueAtTime(freq, ctx.currentTime + i * 0.18);
      gain.gain.setValueAtTime(0.2, ctx.currentTime + i * 0.18);
      gain.gain.exponentialRampToValueAtTime(
        0.001,
        ctx.currentTime + i * 0.18 + 0.15,
      );
      osc.start(ctx.currentTime + i * 0.18);
      osc.stop(ctx.currentTime + i * 0.18 + 0.15);
    });
  } catch (e) {
    /* Audio not supported */
  }
}

// ── STATUS CHECK ────────────────────────────────────────────

fetch("/status")
  .then((r) => r.json())
  .then((d) => {
    document.getElementById("mdl-st").textContent = d.model_loaded
      ? "LOADED"
      : "MISSING";
    document.getElementById("mdl-st").className =
      "sbadge " + (d.model_loaded ? "ok" : "err");
    document.getElementById("scl-st").textContent = d.scaler_loaded
      ? "LOADED"
      : "MISSING";
    document.getElementById("scl-st").className =
      "sbadge " + (d.scaler_loaded ? "ok" : "err");
    if (!d.model_loaded)
      showToast("warning", "⚠️ Model Missing", "Check models/ directory.");
    if (!d.scaler_loaded)
      showToast("warning", "⚠️ Scaler Missing", "Detection may be inaccurate.");
  })
  .catch(() => showToast("info", "ℹ️ Status", "Could not reach /status."));

// ── STARTUP TOAST ───────────────────────────────────────────
setTimeout(
  () =>
    showToast(
      "success",
      "🏥 FallGuard Ready",
      "System initialised. Monitoring active.",
    ),
  800,
);
