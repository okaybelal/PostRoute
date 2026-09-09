"""Route-covering algorithms for the postal delivery problem.

Given an undirected street graph, a postal carrier must traverse every
street (edge) at least once and return to the depot, at minimum total
weight (distance or travel_time). This is the classic Chinese Postman
Problem (Route Inspection Problem).
"""

import itertools
import random

import networkx as nx


def edge_weight(G, u, v):
    """Weight of one u-v edge, whether G is a Graph or MultiGraph."""
    data = G[u][v]
    if G.is_multigraph():
        return next(iter(data.values()))["weight"]
    return data["weight"]


def route_cost(G, route):
    """Total weight of a node sequence route, summed over edge weights."""
    total = 0.0
    for u, v in zip(route[:-1], route[1:]):
        total += edge_weight(G, u, v)
    return total


def _as_simple_weighted(G):
    """Collapse a MultiGraph to a simple Graph keeping the min-weight edge."""
    H = nx.Graph()
    H.add_nodes_from(G.nodes(data=True))
    for u, v, data in G.edges(data=True):
        w = data.get("weight", data.get("length", 1))
        if H.has_edge(u, v):
            if w < H[u][v]["weight"]:
                H[u][v]["weight"] = w
        else:
            H.add_edge(u, v, weight=w)
    return H


def chinese_postman(G, source=None):
    """Optimal solution: eulerize the graph (min-weight matching on odd
    vertices) then take an Eulerian circuit. This is what real-world
    route-inspection solvers use in practice.
    """
    H = _as_simple_weighted(G)
    if source is None:
        source = next(iter(H.nodes))

    eulerized = nx.eulerize(H)
    circuit = list(nx.eulerian_circuit(eulerized, source=source))
    route = [circuit[0][0]] + [v for _, v in circuit]
    return route, route_cost(eulerized, route)


def fleury(G, source=None):
    """Fleury's algorithm: repeatedly walk an edge that isn't a bridge
    (unless it's the only option), removing edges as they're used.
    Requires the graph to already be Eulerian (0 or 2 odd-degree nodes);
    non-Eulerian graphs are first eulerized like chinese_postman does.
    """
    H = _as_simple_weighted(G)
    eulerized = nx.eulerize(H)
    work = eulerized.copy()

    odd = [n for n, d in work.degree() if d % 2 == 1]
    if source is None:
        source = odd[0] if odd else next(iter(work.nodes))

    route = [source]
    current = source
    while work.number_of_edges() > 0:
        neighbors = list(work.neighbors(current))
        if not neighbors:
            break
        if len(neighbors) == 1:
            nxt = neighbors[0]
        else:
            nxt = None
            for cand in neighbors:
                work.remove_edge(current, cand)
                still_connected = nx.has_path(work, current, cand) if work.degree(current) else True
                work.add_edge(current, cand, weight=edge_weight(eulerized, current, cand))
                if still_connected:
                    nxt = cand
                    break
            nxt = nxt or neighbors[0]
        route.append(nxt)
        work.remove_edge(current, nxt)
        current = nxt

    return route, route_cost(eulerized, route)


def _naive_edge_cover(G, source, strategy="dfs"):
    """Heuristic baseline: walk a DFS/BFS tree over the eulerized graph,
    backtracking (retracing edges) whenever a dead end is hit. Simpler
    than Fleury/CPP but typically costs more retraced distance.
    """
    H = _as_simple_weighted(G)
    eulerized = nx.eulerize(H)
    visited_edges = set()
    route = [source]

    def edge_key(u, v):
        return (u, v) if u <= v else (v, u)

    def walk(u):
        neighbors = list(eulerized.neighbors(u))
        if strategy == "bfs":
            random.shuffle(neighbors)
        for v in neighbors:
            key = edge_key(u, v)
            if key not in visited_edges:
                visited_edges.add(key)
                route.append(v)
                walk(v)
                route.append(u)

    walk(source)
    return route, route_cost(eulerized, route)


def dfs_cover(G, source=None):
    H = _as_simple_weighted(G)
    if source is None:
        source = next(iter(H.nodes))
    return _naive_edge_cover(G, source, strategy="dfs")


def bfs_cover(G, source=None):
    H = _as_simple_weighted(G)
    if source is None:
        source = next(iter(H.nodes))
    return _naive_edge_cover(G, source, strategy="bfs")


ALGORITHMS = {
    "cpp": chinese_postman,
    "fleury": fleury,
    "dfs": dfs_cover,
    "bfs": bfs_cover,
}
