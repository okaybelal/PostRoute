# PostRoute

Find the cost-effective route for a postal carrier to cover every street in a city at least once, using real street-network data.

This is the **Chinese Postman Problem** (Route Inspection Problem): given a city's road graph, find the minimum-cost closed walk that traverses every edge (street) at least once. It's the same underlying problem that governs snow plowing, street sweeping, garbage collection, and mail delivery — here applied to postal routing.

Built with `osmnx`, `networkx`, `pandas`, `numpy`, and `plotly`.

## Setup

```
pip install -r requirements.txt
```

## Usage

### Web app

```
python app.py
```

Open `http://localhost:5050`, type a city and country, pick a weight metric and algorithm, and hit **Solve route**. Stats and the interactive map render right in the page. The solve runs live (real OSMnx download), so larger cities can take a while.

### CLI

```
python script.py --city <city> --country <country> --weight_name length --algorithm cpp
```

- `--weight_name`: `length` (distance) or `travel_time`
- `--algorithm`: `cpp` (optimal, min-weight-matching Eulerian augmentation), `fleury` (Fleury's algorithm), `dfs`/`bfs` (naive edge-covering heuristics for comparison)

Example:

```
python script.py --city "Le Plateau-Mont-Royal" --country Canada --weight_name length --algorithm cpp
```

For a smaller/faster test area, try a borough or a small town rather than a whole metro area — OSMnx downloads the full street graph for the given place.

Running it prints network/route stats and opens an interactive map (`route_map.html`) tracing the carrier's route.
