"""PostRoute web app: pick a city, algorithm, and weight metric in the
browser and get back the solved delivery route on an interactive map,
with live progress while it solves.

Architecture: POST /api/solve starts the actual solve (build_graph +
the chosen algorithm from algorithms.ALGORITHMS) on a background thread
and returns a job_id immediately; GET /api/solve/status/<job_id> is
polled by the frontend every ~700ms for live progress messages and the
final result. Job state lives in the in-memory `jobs` dict below, which
is why this must run as a single worker process (see Procfile/render.yaml)
- multiple processes would each have their own copy of `jobs`, so a
status poll could land on a worker that never saw the job that started it.
"""

import json
import logging
import os
import threading
import uuid

import plotly.utils
from flask import Flask, jsonify, render_template, request

from algorithms import ALGORITHMS
from script import build_graph
from utils import build_figure, build_stats

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("postroute")

# In-memory job store — requires running as a single worker process (see
# Procfile/render.yaml: --workers 1 --threads N). With multiple worker
# processes, a status poll could land on a worker that never saw the job.
jobs = {}
jobs_lock = threading.Lock()


def _run_job(job_id, city, country, weight_name, algorithm):
    def progress(msg, frac=None):
        with jobs_lock:
            jobs[job_id]["messages"].append(msg)
            if frac is not None:
                jobs[job_id]["progress"] = frac

    try:
        G = build_graph(city, country, weight_name, progress=progress)
    except Exception:
        logger.exception("build_graph failed for city=%r country=%r", city, country)
        with jobs_lock:
            jobs[job_id]["status"] = "error"
            jobs[job_id]["error"] = (
                f"Couldn't find or download a street network for \"{city}, {country}\". "
                "Try being more specific (e.g. a borough/neighborhood plus city and country)."
            )
        return

    if G.number_of_edges() == 0:
        with jobs_lock:
            jobs[job_id]["status"] = "error"
            jobs[job_id]["error"] = f"No drivable streets found for \"{city}, {country}\"."
        return

    try:
        route, cost = ALGORITHMS[algorithm](G, progress=progress)
    except Exception:
        logger.exception("Solving failed for job_id=%s city=%r country=%r algorithm=%r", job_id, city, country, algorithm)
        with jobs_lock:
            jobs[job_id]["status"] = "error"
            jobs[job_id]["error"] = "Solving failed for that street network. Try a different area or algorithm."
        return

    stats = build_stats(G, route, cost, algorithm, weight_name)
    fig = build_figure(G, route, f"{city}, {country}", algorithm)
    figure_dict = json.loads(plotly.utils.PlotlyJSONEncoder().encode(fig))

    with jobs_lock:
        jobs[job_id]["status"] = "done"
        jobs[job_id]["progress"] = 1.0
        jobs[job_id]["result"] = {"stats": stats, "figure": figure_dict}


@app.route("/")
def index():
    return render_template("index.html", algorithms=list(ALGORITHMS.keys()))


@app.route("/api/solve", methods=["POST"])
def solve():
    payload = request.get_json(force=True) or {}
    city = (payload.get("city") or "").strip()
    country = (payload.get("country") or "").strip()
    weight_name = payload.get("weight_name", "length")
    algorithm = payload.get("algorithm", "cpp")

    if not city or not country:
        return jsonify(error="City and country are both required."), 400
    if weight_name not in ("length", "travel_time"):
        return jsonify(error="weight_name must be 'length' or 'travel_time'."), 400
    if algorithm not in ALGORITHMS:
        return jsonify(error=f"Unknown algorithm '{algorithm}'."), 400

    job_id = uuid.uuid4().hex
    jobs[job_id] = {"status": "running", "messages": [], "result": None, "error": None, "progress": 0.0}

    thread = threading.Thread(target=_run_job, args=(job_id, city, country, weight_name, algorithm), daemon=True)
    thread.start()

    return jsonify(job_id=job_id)


@app.route("/api/solve/status/<job_id>")
def solve_status(job_id):
    job = jobs.get(job_id)
    if job is None:
        return jsonify(error="Unknown job."), 404

    with jobs_lock:
        return jsonify(
            status=job["status"],
            messages=job["messages"],
            progress=job["progress"],
            result=job["result"],
            error=job["error"],
        )


if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    port = int(os.environ.get("PORT", 5050))
    app.run(debug=debug, port=port, threaded=True)
