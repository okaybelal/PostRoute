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


def _apply_weights(G, weight_name):
    for u, v, data in G.edges(data=True):
        data["weight"] = data.get(weight_name, data.get("length", 1))
    return G


def build_graph(city, country, weight_name):
    place = f"{city}, {country}"
    G = ox.graph_from_place(place, network_type="drive", simplify=True)
    G = ox.convert.to_undirected(G)
    return _apply_weights(G, weight_name)


def build_graph_from_file(osm_file_path, weight_name):
    """Load a street network from a local OSM XML extract instead of the
    live Overpass API. For a very large area (a big metro, or a whole
    region), a single Overpass query for the place polygon can be slow or
    get rate-limited — downloading an extract once (e.g. from
    https://extract.bbbike.org, or a Geofabrik .osm.pbf converted to XML
    with `osmium cat -f osm in.pbf -o out.osm`) and loading it locally
    avoids that entirely.
    """
    G = ox.graph_from_xml(osm_file_path, simplify=True)
    G = ox.convert.to_undirected(G)
    return _apply_weights(G, weight_name)


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

    if args.osm_file:
        print(f"Loading street network from {args.osm_file} ...")
        G = build_graph_from_file(args.osm_file, args.weight_name)
        place_label = args.city or args.osm_file
    else:
        if not args.city or not args.country:
            parser.error("--city and --country are required unless --osm-file is given")
        print(f"Downloading street network for {args.city}, {args.country} ...")
        G = build_graph(args.city, args.country, args.weight_name)
        place_label = args.city

    solve = ALGORITHMS[args.algorithm]
    print(f"Solving with '{args.algorithm}' ...")
    route, cost = solve(G)

    print_stats(G, route, cost, args.algorithm, args.weight_name)
    out = plot_route(G, route, place_label, args.algorithm)
    print(f"Interactive map written to {out}")


if __name__ == "__main__":
    main()
