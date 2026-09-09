"""PostRoute: find a cost-effective route for a postal carrier to cover
every street in a city at least once (Chinese Postman / Route Inspection
Problem), using real OpenStreetMap street data.

Example:
    python script.py --city "Le Plateau-Mont-Royal" --country Canada --weight_name length --algorithm cpp
"""

import argparse

import osmnx as ox

from algorithms import ALGORITHMS
from utils import plot_route, print_stats

# overpass-api.de (osmnx's default) blocks connections from a number of
# cloud-hosting IP ranges (AWS, GCP, Render, etc.) to deter scraping/abuse.
# Fall back to other public mirrors on a different network if the primary
# one fails — whatever the failure mode turns out to be in practice (a
# refused connection, a DNS hiccup, osmnx's own internal exception types),
# so this deliberately catches broadly per mirror rather than guessing one
# specific exception class.
OVERPASS_MIRRORS = [
    ox.settings.overpass_url,
    "https://overpass.kumi.systems/api",
    "https://overpass.osm.ch/api",
]

# osmnx's own polite-pause logic (checking the server's /status endpoint,
# then sleeping the duration it reports) silently falls back to a 60s
# default pause if that status check itself fails to connect — which just
# burns time against a server that's blocking us anyway. We handle our own
# resilience via OVERPASS_MIRRORS, so skip osmnx's pause step entirely.
ox.settings.overpass_rate_limit = False


def _apply_weights(G, weight_name):
    for u, v, data in G.edges(data=True):
        data["weight"] = data.get(weight_name, data.get("length", 1))
    return G


def _with_overpass_fallback(fetch, progress=None):
    last_error = None
    for i, mirror in enumerate(OVERPASS_MIRRORS):
        ox.settings.overpass_url = mirror
        try:
            return fetch()
        except Exception as e:
            last_error = e
            if progress and i + 1 < len(OVERPASS_MIRRORS):
                progress(
                    f"{mirror} failed ({type(e).__name__}: {e}), trying another Overpass mirror...", 0.0
                )
    raise last_error


def build_graph(city, country, weight_name, progress=None):
    if progress:
        progress(f"Downloading street network for {city}, {country}...", 0.0)
    place = f"{city}, {country}"
    G = _with_overpass_fallback(
        lambda: ox.graph_from_place(place, network_type="drive", simplify=True), progress
    )
    G = ox.convert.to_undirected(G)
    G = _apply_weights(G, weight_name)
    if progress:
        progress(f"Downloaded {G.number_of_edges()} streets, {G.number_of_nodes()} intersections", 0.15)
    return G


def build_graph_from_file(osm_file_path, weight_name, progress=None):
    """Load a street network from a local OSM XML extract instead of the
    live Overpass API. For a very large area (a big metro, or a whole
    region), a single Overpass query for the place polygon can be slow or
    get rate-limited — downloading an extract once (e.g. from
    https://extract.bbbike.org, or a Geofabrik .osm.pbf converted to XML
    with `osmium cat -f osm in.pbf -o out.osm`) and loading it locally
    avoids that entirely.
    """
    if progress:
        progress(f"Loading street network from {osm_file_path}...", 0.0)
    G = ox.graph_from_xml(osm_file_path, simplify=True)
    G = ox.convert.to_undirected(G)
    G = _apply_weights(G, weight_name)
    if progress:
        progress(f"Loaded {G.number_of_edges()} streets, {G.number_of_nodes()} intersections", 0.15)
    return G


def main():
    parser = argparse.ArgumentParser(description="PostRoute — postal delivery route optimizer")
    parser.add_argument("--city", help="City or borough name, e.g. 'Le Plateau-Mont-Royal'")
    parser.add_argument("--country", help="Country name, e.g. 'Canada'")
    parser.add_argument("--osm-file", help="Path to a local .osm XML extract, used instead of "
                                            "--city/--country (skips the live Overpass download)")
    parser.add_argument("--weight_name", default="length", choices=["length", "travel_time"],
                         help="Edge weight to optimize: 'length' or 'travel_time'")
    parser.add_argument("--algorithm", default="cpp", choices=list(ALGORITHMS.keys()),
                         help="Routing algorithm: cpp (optimal), fleury, dfs, bfs")
    args = parser.parse_args()

    def log(msg, frac=None):
        print(msg)

    if args.osm_file:
        G = build_graph_from_file(args.osm_file, args.weight_name, progress=log)
        place_label = args.city or args.osm_file
    else:
        if not args.city or not args.country:
            parser.error("--city and --country are required unless --osm-file is given")
        G = build_graph(args.city, args.country, args.weight_name, progress=log)
        place_label = args.city

    solve = ALGORITHMS[args.algorithm]
    route, cost = solve(G, progress=log)

    print_stats(G, route, cost, args.algorithm, args.weight_name)
    out = plot_route(G, route, place_label, args.algorithm)
    print(f"Interactive map written to {out}")


if __name__ == "__main__":
    main()
