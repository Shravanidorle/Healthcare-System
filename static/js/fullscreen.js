/* ============================================================
   fullscreen.js — Fullscreen feed modal
   ============================================================ */

function openFS(type) {
  const modal = document.getElementById("fs-modal");
  const img = document.getElementById("fs-img");
  const lbl = document.getElementById("fs-lbl");
  const room = ROOMS.find((r) => r.id === curRoom);

  if (type === "cam") {
    img.src = document.getElementById("video-feed").src;
    lbl.textContent = `CAMERA FEED — ${room?.name?.toUpperCase() || "ROOM " + curRoom}`;
  } else {
    img.src = document.getElementById("skel-feed").src;
    lbl.textContent = "SKELETAL VIEW — PRIVACY MODE";
  }

  modal.classList.add("open");
  document.body.style.overflow = "hidden";
}

function closeFS() {
  document.getElementById("fs-modal").classList.remove("open");
  document.body.style.overflow = "";
}

// Close on ESC key
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeFS();
});
