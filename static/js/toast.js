/* ============================================================
   toast.js — Toast notification system
   ============================================================ */

const TOAST_ICONS = {
  success: "✅",
  error: "🚨",
  info: "ℹ️",
  warning: "⚠️",
};

/**
 * Show a toast notification.
 * @param {'success'|'error'|'info'|'warning'} type
 * @param {string} title
 * @param {string} msg
 * @param {number} dur  Duration in ms (default 4000)
 */
function showToast(type, title, msg, dur = 4000) {
  const container = document.getElementById("toast-container");
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.innerHTML = `
        <span class="toast-icon">${TOAST_ICONS[type] || "•"}</span>
        <div class="toast-body">
            <div class="toast-title">${title}</div>
            <div class="toast-msg">${msg}</div>
        </div>
        <button class="toast-close" onclick="killToast(this.parentElement)">✕</button>
        <div class="toast-prog" style="animation-duration:${dur}ms"></div>
    `;
  container.appendChild(el);
  setTimeout(() => killToast(el), dur);
}

function killToast(el) {
  if (!el || el.classList.contains("fade-out")) return;
  el.classList.add("fade-out");
  setTimeout(() => el.remove(), 300);
}
