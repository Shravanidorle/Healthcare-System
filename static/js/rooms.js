/* ============================================================
   rooms.js — Room data, dropdown, selector logic
   ============================================================ */

const ROOMS = [
  { id: "101", name: "Room 101", patient: "Priya Sharma", status: "live" },
  { id: "102", name: "Room 102", patient: "Arjun Mehta", status: "live" },
  { id: "103", name: "Room 103", patient: "Sunita Rao", status: "offline" },
  { id: "104", name: "Room 104", patient: "Vikram Singh", status: "offline" },
  { id: "ICU", name: "ICU Bay 1", patient: "Kavya Nair", status: "live" },
];

let curRoom = "101";

function buildRooms() {
  const dd = document.getElementById("room-dd");
  const dlr = document.getElementById("drw-rooms");
  dd.innerHTML = "";
  dlr.innerHTML = "";

  ROOMS.forEach((r) => {
    const isActive = r.id === curRoom;
    const dot = `<div class="rdot ${r.status === "live" ? "live" : "off"}"></div>`;
    const tag = `<span class="rtag ${r.status === "live" ? "live" : "off"}">${r.status.toUpperCase()}</span>`;
    const info = `<div class="rinfo"><div class="rname">${r.name}</div><div class="rpatient">${r.patient}</div></div>`;

    // Header dropdown option
    const opt = document.createElement("div");
    opt.className = "room-opt" + (isActive ? " active" : "");
    opt.innerHTML = dot + info + tag;
    opt.onclick = (e) => {
      e.stopPropagation();
      selectRoom(r.id);
    };
    dd.appendChild(opt);

    // Drawer room list option
    const dopt = document.createElement("div");
    dopt.className = "nav-item" + (isActive ? " active" : "");
    dopt.style.marginBottom = "3px";
    dopt.innerHTML = `${dot}<div style="flex:1"><div style="font-size:0.82em">${r.name}</div><div style="font-size:0.7em;color:var(--muted)">${r.patient}</div></div>${tag}`;
    dopt.onclick = () => {
      selectRoom(r.id);
      closeDrawer();
    };
    dlr.appendChild(dopt);
  });
}

function selectRoom(id) {
  const r = ROOMS.find((x) => x.id === id);
  if (!r) return;
  curRoom = id;
  document.getElementById("cur-room").textContent = id;
  closeRoomDD();
  buildRooms();
  showToast(
    "info",
    "📍 Room Changed",
    `Now monitoring ${r.name} — ${r.patient}`,
  );
}

function toggleRoomDD() {
  document.getElementById("room-dd").classList.toggle("open");
}
function closeRoomDD() {
  document.getElementById("room-dd").classList.remove("open");
}

// Close dropdown when clicking outside
document.addEventListener("click", (e) => {
  if (!document.getElementById("room-sel-btn").contains(e.target))
    closeRoomDD();
});
