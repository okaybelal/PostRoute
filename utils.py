"""Map plotting and stats reporting for PostRoute."""

import networkx as nx
import osmnx as ox
import plotly.graph_objects as go


def route_to_latlon(G, route):
    lats, lons = [], []
    for node in route:
        data = G.nodes[node]
        lats.append(data["y"])
        lons.append(data["x"])
    return lats, lons


def plot_route(G, route, city, algorithm_name, out_html="route_map.html"):
    lats, lons = route_to_latlon(G, route)

    fig = go.Figure()

    # base street network, as one trace with None separators between segments
    base_lat, base_lon = [], []
    for u, v in G.edges():
        y0, x0 = G.nodes[u]["y"], G.nodes[u]["x"]
        y1, x1 = G.nodes[v]["y"], G.nodes[v]["x"]
        base_lat += [y0, y1, None]
        base_lon += [x0, x1, None]

    fig.add_trace(
        go.Scattermap(
            lat=base_lat, lon=base_lon,
            mode="lines",
            line=dict(width=1, color="lightgray"),
            hoverinfo="skip",
            showlegend=False,
        )
    )

    # delivery route, traced in order
    fig.add_trace(
        go.Scattermap(
            lat=lats, lon=lons,
            mode="lines+markers",
            line=dict(width=3, color="crimson"),
            marker=dict(size=4),
            name=f"{algorithm_name} route",
        )
    )

    center_lat = sum(lats) / len(lats)
    center_lon = sum(lons) / len(lons)

    fig.update_layout(
        map=dict(style="open-street-map", center=dict(lat=center_lat, lon=center_lon), zoom=13),
        title=f"PostRoute — {algorithm_name} delivery route for {city}",
        margin=dict(l=0, r=0, t=40, b=0),
    )

    fig.write_html(out_html)
    fig.show()
    return out_html


def print_stats(G, route, cost, algorithm_name, weight_name):
    unit = "meters" if weight_name == "length" else "seconds"
    print("=" * 50)
    print(f"Algorithm: {algorithm_name}")
    print(f"Streets in network (edges): {G.number_of_edges()}")
    print(f"Intersections (nodes): {G.number_of_nodes()}")
    print(f"Stops on route: {len(route)}")
    print(f"Total route cost ({unit}): {cost:.1f}")
    if weight_name == "length":
        print(f"Total route distance (km): {cost / 1000:.2f}")
    else:
        print(f"Total route time (min): {cost / 60:.1f}")
    print("=" * 50)
