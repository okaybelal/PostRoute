const ALGO_HINTS = {
  cpp: "Optimal: minimum-weight matching to eulerize the graph, then an Eulerian circuit.",
  fleury: "Classic Eulerian-circuit walk that avoids stranding bridges — matches cpp's cost.",
  dfs: "Naive depth-first edge cover with backtracking. Simple, usually costs more than cpp.",
  bfs: "Naive breadth-first-flavored edge cover with backtracking. Simple, usually costs more.",
};

const POLL_INTERVAL_MS = 700;

const form = document.getElementById("solve-form");
const btn = document.getElementById("solve-btn");
const statusEl = document.getElementById("status");
const progressLogEl = document.getElementById("progress-log");
const progressBarEl = document.getElementById("progress-bar");
const progressBarFillEl = document.getElementById("progress-bar-fill");
const errorEl = document.getElementById("error");
const statsEl = document.getElementById("stats");
const algoSelect = document.getElementById("algorithm");
const algoHint = document.getElementById("algo-hint");

let pollTimer = null;
let renderedCount = 0;

function updateAlgoHint() {
  algoHint.textContent = ALGO_HINTS[algoSelect.value] || "";
}
algoSelect.addEventListener("change", updateAlgoHint);
updateAlgoHint();

function setLoading(loading) {
  btn.disabled = loading;
  statusEl.hidden = !loading;
  if (loading) {
    progressLogEl.innerHTML = "";
    renderedCount = 0;
    progressBarFillEl.style.width = "";
    progressBarEl.classList.add("indeterminate");
  }
}

function appendMessages(messages) {
  for (; renderedCount < messages.length; renderedCount++) {
    const line = document.createElement("div");
    line.textContent = messages[renderedCount];
    progressLogEl.appendChild(line);
  }
  progressLogEl.scrollTop = progressLogEl.scrollHeight;

  updateProgressBar(messages[messages.length - 1]);
}

function updateProgressBar(lastMessage) {
  // Reflect the real "done/total" fraction from the backend's own
  // progress messages when one is present — no fabricated percentage.
  const match = lastMessage && lastMessage.match(/(\d+)\/(\d+)/);
  if (match) {
    const pct = Math.min(100, (Number(match[1]) / Number(match[2])) * 100);
    progressBarEl.classList.remove("indeterminate");
    progressBarFillEl.style.width = `${pct}%`;
  } else {
    progressBarEl.classList.add("indeterminate");
    progressBarFillEl.style.width = "";
  }
}

function renderStats(stats) {
  document.getElementById("stat-streets").textContent = stats.streets.toLocaleString();
  document.getElementById("stat-intersections").textContent = stats.intersections.toLocaleString();
  document.getElementById("stat-stops").textContent = stats.stops.toLocaleString();

  if (stats.distance_km !== undefined) {
    document.getElementById("stat-cost").textContent = `${stats.distance_km.toLocaleString()} km`;
    document.getElementById("stat-cost-label").textContent = "total distance";
  } else {
    document.getElementById("stat-cost").textContent = `${stats.time_min.toLocaleString()} min`;
    document.getElementById("stat-cost-label").textContent = "total time";
  }
  statsEl.hidden = false;
}

function stopPolling() {
  if (pollTimer !== null) {
    clearTimeout(pollTimer);
    pollTimer = null;
  }
}

async function pollStatus(jobId) {
  let data;
  try {
    const res = await fetch(`/api/solve/status/${jobId}`);
    data = await res.json();
    if (!res.ok) throw new Error(data.error || "Lost track of that job.");
  } catch (err) {
    // transient network hiccup — just retry on the next tick
    pollTimer = setTimeout(() => pollStatus(jobId), POLL_INTERVAL_MS);
    return;
  }

  appendMessages(data.messages || []);

  if (data.status === "running") {
    pollTimer = setTimeout(() => pollStatus(jobId), POLL_INTERVAL_MS);
    return;
  }

  setLoading(false);

  if (data.status === "done") {
    renderStats(data.result.stats);
    Plotly.newPlot("map", data.result.figure.data, data.result.figure.layout, { responsive: true });
  } else {
    errorEl.textContent = data.error || "Something went wrong.";
    errorEl.hidden = false;
  }
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  stopPolling();
  errorEl.hidden = true;
  statsEl.hidden = true;

  const payload = {
    city: document.getElementById("city").value.trim(),
    country: document.getElementById("country").value.trim(),
    weight_name: document.getElementById("weight_name").value,
    algorithm: algoSelect.value,
  };

  setLoading(true);

  try {
    const res = await fetch("/api/solve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.error || "Something went wrong.");
    }

    pollStatus(data.job_id);
  } catch (err) {
    setLoading(false);
    errorEl.textContent = err.message || "Something went wrong.";
    errorEl.hidden = false;
  }
});
