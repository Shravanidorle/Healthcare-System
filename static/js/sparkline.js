/* ============================================================
   sparkline.js — Live confidence trend chart (Chart.js)
   ============================================================ */

const SPARK_POINTS = 60;
const sparkData = Array(SPARK_POINTS).fill(0);
let sparkChart;

function initSparkline() {
  const ctx = document.getElementById("spark-canvas").getContext("2d");
  const grad = buildGrad(ctx, false);

  sparkChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: Array(SPARK_POINTS).fill(""),
      datasets: [
        {
          data: [...sparkData],
          borderColor: "#00e57a",
          borderWidth: 1.5,
          backgroundColor: grad,
          fill: true,
          tension: 0.4,
          pointRadius: 0,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 280 },
      plugins: { legend: { display: false }, tooltip: { enabled: false } },
      scales: {
        x: { display: false },
        y: {
          display: true,
          min: 0,
          max: 100,
          grid: { color: "rgba(255,255,255,0.04)", drawBorder: false },
          ticks: {
            color: "rgba(80,96,112,0.9)",
            font: { family: "'Space Mono'", size: 8 },
            maxTicksLimit: 3,
            callback: (v) => v + "%",
          },
        },
      },
    },
  });
}

function buildGrad(ctx, danger) {
  const g = ctx.createLinearGradient(0, 0, 0, 68);
  g.addColorStop(0, danger ? "rgba(255,59,92,0.28)" : "rgba(0,229,122,0.28)");
  g.addColorStop(1, "rgba(0,0,0,0)");
  return g;
}

/**
 * Push a new confidence value onto the sparkline.
 * @param {number} v  Confidence value 0–100
 */
function pushSpark(v) {
  sparkData.push(v);
  if (sparkData.length > SPARK_POINTS) sparkData.shift();

  const danger = v >= 85;
  const ctx = document.getElementById("spark-canvas").getContext("2d");

  sparkChart.data.datasets[0].data = [...sparkData];
  sparkChart.data.datasets[0].borderColor = danger ? "#ff3b5c" : "#00e57a";
  sparkChart.data.datasets[0].backgroundColor = buildGrad(ctx, danger);
  sparkChart.update("none");

  const el = document.getElementById("spark-live");
  el.textContent = v.toFixed(1) + "%";
  el.className = "spark-val" + (danger ? " danger" : "");
}

// Keep chart ticking every second even without new data
setInterval(() => pushSpark(sparkData[sparkData.length - 1] || 0), 1000);
