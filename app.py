"""Flask app: browse a Letterboxd watchlist filtered by streaming availability."""
from flask import Flask, jsonify, render_template, request

import db
import pipeline
import tmdb
from config import DEFAULT_SERVICE_ID, LETTERBOXD_USERNAME, REGION, tmdb_configured

app = Flask(__name__)
db.init_db()

# TMDB's list of watch-provider regions (code -> name). Loaded lazily & cached.
_regions_cache = None


def _all_regions():
    global _regions_cache
    if _regions_cache is None and tmdb_configured():
        try:
            _regions_cache = tmdb.get_provider_regions()
        except Exception:  # noqa: BLE001
            _regions_cache = []
    return _regions_cache or []


@app.route("/")
def index():
    return render_template(
        "index.html",
        username=LETTERBOXD_USERNAME,
        default_region=REGION,
        default_service=DEFAULT_SERVICE_ID,
        tmdb_ok=tmdb_configured(),
    )


@app.route("/api/options")
def api_options():
    """Regions and services available to filter by, given the current watchlist."""
    films = db.all_films()
    present = db.available_regions(films)

    # Region dropdown: TMDB's full region list, marking which ones actually have
    # any of your films available (so the UI can prioritise / label them).
    region_names = {r["code"]: r["name"] for r in _all_regions()}
    for code in present:
        region_names.setdefault(code, code)
    regions = [
        {"code": code, "name": name, "available": code in present}
        for code, name in region_names.items()
    ]
    regions.sort(key=lambda r: (not r["available"], r["name"].lower()))

    region = (request.args.get("region") or REGION).upper()
    services = db.services_for_region(films, region)
    return jsonify({"regions": regions, "services": services})


@app.route("/api/films")
def api_films():
    region = (request.args.get("region") or REGION).upper()
    service = request.args.get("service")  # provider id, or "" / "any" for all

    films = db.all_films()
    matched = [f for f in films if db.film_available(f, region, service)]

    q = (request.args.get("q") or "").strip().lower()
    if q:
        matched = [f for f in matched if q in (f["title"] or "").lower()]

    # Attach the region-specific provider list each card should display.
    out = []
    for f in matched:
        out.append(
            {
                "slug": f["slug"],
                "title": f["title"],
                "year": f["year"],
                "poster_path": f["poster_path"],
                "providers": db.region_providers(f, region),
            }
        )

    return jsonify(
        {
            "films": out,
            "counts": {**db.counts(), "matched": len(out)},
        }
    )


@app.route("/api/status")
def api_status():
    snap = pipeline.state.snapshot()
    snap["counts"] = db.counts()
    return jsonify(snap)


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    if not tmdb_configured():
        return jsonify({"error": "TMDB credentials not configured. See .env.example."}), 400
    force = request.args.get("force") == "1"
    started = pipeline.start_refresh(force=force)
    return jsonify({"started": started, **pipeline.state.snapshot()})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
