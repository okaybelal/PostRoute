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
- `--algorithm`: `cpp` (optimal, min-weight-matching Eulerian augmentation), `fleury` (Fleury's algorithm — same cost as `cpp`), `dfs`/`bfs` (cheap non-optimal heuristics — no matching step at all, so they stay fast even on huge graphs)
- `--osm-file`: load a local `.osm` XML extract instead of downloading via the live Overpass API (see **Large areas** below); when given, `--city`/`--country` become optional (just used as a label)

Example:

```
python script.py --city "Le Plateau-Mont-Royal" --country Canada --weight_name length --algorithm cpp
```

For a smaller/faster test area, try a borough or a small town rather than a whole metro area — OSMnx downloads the full street graph for the given place.

Running it prints network/route stats and opens an interactive map (`route_map.html`) tracing the carrier's route.

## Performance notes

`cpp`/`fleury` need to pair up every odd-degree intersection (a graph can only be traversed in one loop if every intersection has an even number of streets meeting there) via a minimum-weight matching. That matching is computed exactly for up to 300 odd-degree intersections — true optimal, and fine for anything from a small town up to a mid-size city. Above that (a big metro area), each odd intersection is matched against only its 10 nearest odd neighbors instead of all of them, trading a small amount of optimality for tractability — without this, the matching cost grows quadratically with the number of odd intersections and becomes intractable at metro scale.

If you just need *a* route fast and don't need the shortest one, `dfs`/`bfs` skip the matching step entirely and stay fast regardless of city size.

### Large areas

For a whole big metro area or region, a single live Overpass API query for the place polygon can be slow or get rate-limited. Instead, download an extract once and load it locally:

```
python script.py --osm-file path/to/extract.osm --weight_name length --algorithm cpp
```

Get an `.osm` XML extract from [bbbike.org's extract service](https://extract.bbbike.org/) (draw the area you want), or convert a Geofabrik `.osm.pbf` regional extract with `osmium cat -f osm in.pbf -o out.osm` (requires the `osmium` command-line tool). This isn't wired into the web app yet — CLI only.

## Deploying the web app

The repo is set up to deploy to [Render](https://render.com) as-is:

1. Push to GitHub (already done for this repo).
2. On Render: **New > Blueprint**, point it at this repo. It reads [render.yaml](render.yaml) and configures everything automatically (build command, start command, free plan).
   - Alternatively, **New > Web Service** manually: build command `pip install -r requirements.txt`, start command from [Procfile](Procfile).
3. Deploy. Render gives you a public `https://<name>.onrender.com` URL.

A couple of things specific to this app's deploy config:

- **Single worker, multiple threads.** [app.py](app.py) keeps each solve's live-progress state in an in-memory dict (`jobs`), shared by the background thread doing the solve and the polling requests checking on it. That only works if every request hits the *same* process — so the [Procfile](Procfile)/[render.yaml](render.yaml) run gunicorn with `--workers 1 --threads 4`, not multiple worker processes. Don't bump `--workers` above 1 without also moving `jobs` to something shared across processes (e.g. Redis).
- **Free tier sleeps, not expires.** Render's free plan spins the service down after 15 minutes with no traffic, and spins it back up on the next request (~30-50s cold start). It doesn't get deleted or stop working after some fixed period — but the first request after a quiet stretch will feel slow (cold start + the solve itself).
- `runtime.txt` pins the Python version for the build; `FLASK_DEBUG=0` (set in `render.yaml`) keeps the Werkzeug debugger off in production — `app.py` only enables it when `FLASK_DEBUG` is unset or `"1"`, which is the default for local `python app.py` runs.
