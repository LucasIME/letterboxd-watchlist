"""Flask app: browse a Letterboxd watchlist filtered by streaming availability."""
from flask import Flask, jsonify, render_template, request

import db
import pipeline
from config import LETTERBOXD_USERNAME, REGION, tmdb_configured

app = Flask(__name__)
db.init_db()


@app.route("/")
def index():
    return render_template(
        "index.html",
        username=LETTERBOXD_USERNAME,
        region=REGION,
        tmdb_ok=tmdb_configured(),
    )


@app.route("/api/films")
def api_films():
    films = db.all_films()
    if request.args.get("mubi") == "1":
        films = [f for f in films if f["on_mubi"]]
    q = (request.args.get("q") or "").strip().lower()
    if q:
        films = [f for f in films if q in (f["title"] or "").lower()]
    return jsonify({"films": films, "counts": db.counts()})


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
