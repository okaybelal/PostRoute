"""PostRoute web app: pick a city, algorithm, and weight metric in the
browser and get back the solved delivery route on an interactive map.
"""

import json

import plotly.utils
from flask import Flask, jsonify, render_template, request

from algorithms import ALGORITHMS
from script import build_graph
from utils import build_figure, build_stats

app = Flask(__name__)


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

    try:
        G = build_graph(city, country, weight_name)
    except Exception:
        return jsonify(
            error=f"Couldn't find or download a street network for \"{city}, {country}\". "
                  "Try being more specific (e.g. a borough/neighborhood plus city and country)."
        ), 400

    if G.number_of_edges() == 0:
        return jsonify(error=f"No drivable streets found for \"{city}, {country}\"."), 400

    try:
        route, cost = ALGORITHMS[algorithm](G)
    except Exception:
        return jsonify(error="Solving failed for that street network. Try a different area or algorithm."), 500

    stats = build_stats(G, route, cost, algorithm, weight_name)
    fig = build_figure(G, route, f"{city}, {country}", algorithm)
    figure_dict = json.loads(plotly.utils.PlotlyJSONEncoder().encode(fig))

    return jsonify(stats=stats, figure=figure_dict)


if __name__ == "__main__":
    app.run(debug=True, port=5050)
