/* ============================================================
   export.js — PDF and CSV report generation
   ============================================================ */

const alertHist = []; // shared alert history array

function exportCSV() {
  if (!alertHist.length) {
    showToast("warning", "⚠️ Empty Log", "No alerts recorded yet.");
    return;
  }

  const rows = [["Timestamp", "Room", "Patient", "Event", "Confidence (%)"]];
  alertHist.forEach((a) =>
    rows.push([a.time, a.room, a.patient, a.msg, a.conf]),
  );
  const csv = rows.map((r) => r.map((c) => `"${c}"`).join(",")).join("\n");

  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
  a.download = "fallguard_log.csv";
  a.click();

  showToast(
    "success",
    "📊 CSV Exported",
    `${alertHist.length} alert(s) saved.`,
  );
  closeDrawer();
}

function exportPDF() {
  if (!alertHist.length) {
    showToast("warning", "⚠️ Empty Log", "No alerts recorded yet.");
    return;
  }

  const room = ROOMS.find((r) => r.id === curRoom);
  const dur = document.getElementById("sess-time").textContent;
  const rows = alertHist
    .map(
      (a, i) => `
        <tr>
            <td>${i + 1}</td>
            <td>${a.time}</td>
            <td>${a.room}</td>
            <td>${a.patient}</td>
            <td>${a.msg}</td>
            <td style="color:#c0392b;font-weight:700">${a.conf}%</td>
        </tr>
    `,
    )
    .join("");

  const html = `<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
    body  { font-family:'Segoe UI',sans-serif; padding:30px; color:#111; }
    h1    { font-size:1.3em; color:#1a1a2e; margin-bottom:4px; }
    .meta { font-size:0.8em; color:#555; margin-bottom:18px; }
    .badge{ background:#c0392b; color:#fff; padding:2px 9px; border-radius:10px; font-size:0.75em; }
    table { width:100%; border-collapse:collapse; font-size:0.82em; }
    th    { background:#1a1a2e; color:#fff; padding:7px 9px; text-align:left; }
    td    { padding:6px 9px; border-bottom:1px solid #e0e0e0; }
    tr:nth-child(even) td { background:#f7f7f7; }
    .foot { margin-top:20px; font-size:0.72em; color:#999; border-top:1px solid #ddd; padding-top:10px; }
</style>
</head>
<body>
    <h1>🏥 FallGuard — Session Alert Report</h1>
    <div class="meta">
        Generated: ${new Date().toLocaleString()} &nbsp;|&nbsp;
        Room: <strong>${room?.name || curRoom}</strong> &nbsp;|&nbsp;
        Patient: <strong>${room?.patient || "N/A"}</strong> &nbsp;|&nbsp;
        Duration: <strong>${dur}</strong><br>
        Total Falls Detected: <span class="badge">${alertHist.length}</span>
    </div>
    <table>
        <thead>
            <tr><th>#</th><th>Time</th><th>Room</th><th>Patient</th><th>Event</th><th>Confidence</th></tr>
        </thead>
        <tbody>${rows}</tbody>
    </table>
    <div class="foot">FallGuard v2.2 · CNN+LSTM Hybrid · MediaPipe Pose Estimation · Hospital Use Only — Confidential</div>
</body>
</html>`;

  const w = window.open("", "_blank");
  w.document.write(html);
  w.document.close();
  setTimeout(() => w.print(), 400);

  showToast("success", "📄 PDF Report", "Print dialog opened — save as PDF.");
  closeDrawer();
}
