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


def build_graph(city, country, weight_name):
    place = f"{city}, {country}"
    G = ox.graph_from_place(place, network_type="drive", simplify=True)
    G = ox.convert.to_undirected(G)

    for u, v, data in G.edges(data=True):
        data["weight"] = data.get(weight_name, data.get("length", 1))

    return G


def main():
    parser = argparse.ArgumentParser(description="PostRoute — postal delivery route optimizer")
    parser.add_argument("--city", required=True, help="City or borough name, e.g. 'Le Plateau-Mont-Royal'")
    parser.add_argument("--country", required=True, help="Country name, e.g. 'Canada'")
    parser.add_argument("--weight_name", default="length", choices=["length", "travel_time"],
                         help="Edge weight to optimize: 'length' or 'travel_time'")
    parser.add_argument("--algorithm", default="cpp", choices=list(ALGORITHMS.keys()),
                         help="Routing algorithm: cpp (optimal), fleury, dfs, bfs")
    args = parser.parse_args()

    print(f"Downloading street network for {args.city}, {args.country} ...")
    G = build_graph(args.city, args.country, args.weight_name)

    solve = ALGORITHMS[args.algorithm]
    print(f"Solving with '{args.algorithm}' ...")
    route, cost = solve(G)

    print_stats(G, route, cost, args.algorithm, args.weight_name)
    out = plot_route(G, route, args.city, args.algorithm)
    print(f"Interactive map written to {out}")


if __name__ == "__main__":
    main()
