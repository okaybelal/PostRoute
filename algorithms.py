"""Route-covering algorithms for the postal delivery problem.

Given an undirected street graph, a postal carrier must traverse every
street (edge) at least once and return to the depot, at minimum total
weight (distance or travel_time). This is the classic Chinese Postman
Problem (Route Inspection Problem).
"""

import random

import networkx as nx


def _noop(msg, frac=None):
    pass


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


def _eulerize(H, exact_threshold=300, k_nearest=10, progress=None, frac_range=(0.0, 1.0)):
    """Turn H into an Eulerian multigraph by duplicating the minimum-weight
    set of edges needed to fix every odd-degree vertex.

    This replaces networkx's own `nx.eulerize`, which has two problems at
    city scale: it matches odd vertices using unweighted `nx.shortest_path`
    (so it doesn't actually minimize distance/travel_time, just hop count),
    and it computes a shortest path for *every pair* of odd vertices
    (O(k^2) for k odd vertices) before matching over the resulting complete
    graph — intractable once k reaches the thousands (a big metro area).

    Below `exact_threshold` odd vertices, this computes a true weighted
    min-weight matching (still O(k) Dijkstra runs instead of O(k^2)
    unweighted shortest-path calls, so it's a strict improvement even in
    the exact case). Above it, each odd vertex is only matched against its
    `k_nearest` closest odd neighbors, bounding the cost to ~O(k *
    k_nearest) at the expense of a possibly slightly longer (non-optimal)
    route.

    `progress` calls report a fraction linearly rescaled into `frac_range`,
    so the caller controls what share of the overall pipeline this step
    represents.
    """
    progress = progress or _noop
    lo, hi = frac_range

    def scaled(f):
        return lo + (hi - lo) * f

    odd = [n for n, d in H.degree() if d % 2 == 1]
    eulerized = nx.MultiGraph(H)
    if not odd:
        return eulerized

    odd_set = set(odd)
    exact = len(odd) <= exact_threshold
    progress(
        f"Found {len(odd)} odd-degree intersections to pair up "
        f"({'exact' if exact else f'approximate, {k_nearest} nearest each'} matching)",
        scaled(0.05),
    )

    candidates = nx.Graph()
    candidates.add_nodes_from(odd)
    tick = max(1, len(odd) // 10)
    for i, n in enumerate(odd, 1):
        dist, paths = nx.single_source_dijkstra(H, n, weight="weight")
        others = sorted(
            ((d, o) for o, d in dist.items() if o in odd_set and o != n)
        )
        if not exact:
            others = others[:k_nearest]
        for d, o in others:
            if not candidates.has_edge(n, o) or candidates[n][o]["weight"] < -d:
                candidates.add_edge(n, o, weight=-d, path=paths[o])
        if i % tick == 0 or i == len(odd):
            progress(f"Computing shortest paths: {i}/{len(odd)} intersections", scaled(0.05 + 0.55 * i / len(odd)))

    progress("Running minimum-weight matching...", scaled(0.65))
    matching = nx.max_weight_matching(candidates, maxcardinality=True)

    matched = {n for pair in matching for n in pair}
    unmatched = [n for n in odd if n not in matched]
    while len(unmatched) > 1:
        n = unmatched.pop()
        dist, paths = nx.single_source_dijkstra(H, n, weight="weight")
        best = min((o for o in unmatched), key=lambda o: dist.get(o, float("inf")))
        unmatched.remove(best)
        matching = set(matching) | {(n, best)}
        candidates.add_edge(n, best, path=paths[best])

    progress(f"Matched {len(matching)} pairs, duplicating streets to build an Eulerian circuit...", scaled(0.85))
    for m, n in matching:
        path = candidates[m][n]["path"]
        for a, b in zip(path[:-1], path[1:]):
            eulerized.add_edge(a, b, weight=edge_weight(H, a, b))

    return eulerized


def chinese_postman(G, source=None, progress=None):
    """Optimal solution: eulerize the graph (min-weight matching on odd
    vertices) then take an Eulerian circuit. This is what real-world
    route-inspection solvers use in practice.
    """
    progress = progress or _noop
    H = _as_simple_weighted(G)
    if source is None:
        source = next(iter(H.nodes))

    progress("Solving with Chinese Postman (optimal)...", 0.15)
    eulerized = _eulerize(H, progress=progress, frac_range=(0.15, 0.85))
    progress("Walking the Eulerian circuit...", 0.90)
    circuit = list(nx.eulerian_circuit(eulerized, source=source))
    route = [circuit[0][0]] + [v for _, v in circuit]
    progress(f"Route complete: {len(route)} stops", 1.0)
    return route, route_cost(eulerized, route)


def fleury(G, source=None, progress=None):
    """Fleury's algorithm: repeatedly walk an edge that isn't a bridge
    (unless it's the only option), removing edges as they're used.
    Requires the graph to already be Eulerian (0 or 2 odd-degree nodes);
    non-Eulerian graphs are first eulerized like chinese_postman does.
    """
    progress = progress or _noop
    H = _as_simple_weighted(G)
    progress("Solving with Fleury's algorithm...", 0.15)
    eulerized = _eulerize(H, progress=progress, frac_range=(0.15, 0.80))
    work = eulerized.copy()

    odd = [n for n, d in work.degree() if d % 2 == 1]
    if source is None:
        source = odd[0] if odd else next(iter(work.nodes))

    total_edges = work.number_of_edges()
    tick = max(1, total_edges // 10)
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

        walked = total_edges - work.number_of_edges()
        if walked % tick == 0:
            progress(f"Walking the Eulerian circuit: {walked}/{total_edges} streets", 0.80 + 0.18 * walked / total_edges)

    progress(f"Route complete: {len(route)} stops", 1.0)
    return route, route_cost(eulerized, route)


def _edge_key(u, v):
    return (u, v) if u <= v else (v, u)


def _naive_edge_cover(G, source, strategy="dfs", progress=None):
    """Heuristic baseline: greedily walk to any neighbor with an uncovered
    edge, and when stuck (no uncovered edge from the current node), jump
    to the nearest node that still has one via a single weighted Dijkstra
    run. Unlike `_eulerize`, this never pays for a min-weight matching —
    it's the cheap, non-optimal option for graphs too big for `cpp`.
    """
    progress = progress or _noop
    H = _as_simple_weighted(G)
    remaining = {_edge_key(u, v) for u, v in H.edges()}
    total = len(remaining)
    tick = max(1, total // 10)
    route = [source]
    current = source

    progress(f"Solving with {strategy} ({total} streets to cover)...", 0.15)
    while remaining:
        neighbors = [v for v in H.neighbors(current) if _edge_key(current, v) in remaining]
        if neighbors:
            nxt = random.choice(neighbors) if strategy == "bfs" else neighbors[0]
            remaining.discard(_edge_key(current, nxt))
            route.append(nxt)
            current = nxt
        else:
            targets = {n for key in remaining for n in key}
            dist, paths = nx.single_source_dijkstra(H, current, weight="weight")
            nxt_target = min(targets, key=lambda n: dist.get(n, float("inf")))
            path = paths[nxt_target]
            for a, b in zip(path[:-1], path[1:]):
                remaining.discard(_edge_key(a, b))
                route.append(b)
            current = nxt_target

        covered = total - len(remaining)
        if covered % tick == 0 or not remaining:
            progress(f"Covered {covered}/{total} streets", 0.15 + 0.83 * covered / total)

    progress(f"Route complete: {len(route)} stops", 1.0)
    return route, route_cost(H, route)


def dfs_cover(G, source=None, progress=None):
    H = _as_simple_weighted(G)
    if source is None:
        source = next(iter(H.nodes))
    return _naive_edge_cover(G, source, strategy="dfs", progress=progress)


def bfs_cover(G, source=None, progress=None):
    H = _as_simple_weighted(G)
    if source is None:
        source = next(iter(H.nodes))
    return _naive_edge_cover(G, source, strategy="bfs", progress=progress)


ALGORITHMS = {
    "cpp": chinese_postman,
    "fleury": fleury,
    "dfs": dfs_cover,
    "bfs": bfs_cover,
}
