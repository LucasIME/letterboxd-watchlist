"""Minimal TMDB client: fetch movie/tv details + watch providers in one call."""
import requests

from config import TMDB_API_KEY, TMDB_READ_TOKEN

BASE = "https://api.themoviedb.org/3"

# Provider "types" we treat as "available to watch with a subscription / for free"
# (as opposed to rent/buy, which aren't what "available on <service>" means).
AVAILABLE_KINDS = ("flatrate", "free", "ads")

_session = requests.Session()
if TMDB_READ_TOKEN:
    _session.headers.update({"Authorization": f"Bearer {TMDB_READ_TOKEN}"})


def _params(extra: dict | None = None) -> dict:
    p = dict(extra or {})
    # v4 read token goes in the header; v3 key goes in the query string.
    if not TMDB_READ_TOKEN and TMDB_API_KEY:
        p["api_key"] = TMDB_API_KEY
    return p


def get_details_and_providers(tmdb_id: int, media_type: str) -> dict:
    """Return {title, poster_path, providers_by_region}.

    A single TMDB call returns watch providers for *every* country, so we keep
    them all — region filtering then happens locally with no extra requests.

    providers_by_region maps a country code to a grouped dict, e.g.
        {"GB": {"flatrate": [{"id": 11, "name": "Mubi"}], "rent": [...]}, ...}
    """
    media_type = media_type if media_type in ("movie", "tv") else "movie"
    url = f"{BASE}/{media_type}/{tmdb_id}"
    resp = _session.get(
        url,
        params=_params({"append_to_response": "watch/providers"}),
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    title = data.get("title") or data.get("name")
    poster_path = data.get("poster_path")

    results = data.get("watch/providers", {}).get("results", {})
    providers_by_region = {}
    for region, region_data in results.items():
        grouped = {}
        for kind in ("flatrate", "free", "ads", "rent", "buy"):
            entries = region_data.get(kind) or []
            if entries:
                grouped[kind] = [
                    {"id": e.get("provider_id"), "name": e.get("provider_name")}
                    for e in entries
                ]
        if grouped:
            providers_by_region[region] = grouped

    return {
        "title": title,
        "poster_path": poster_path,
        "providers_by_region": providers_by_region,
    }


def get_provider_regions() -> list[dict]:
    """List of watch-provider countries: [{code, name}], sorted by name."""
    resp = _session.get(
        f"{BASE}/watch/providers/regions",
        params=_params({"language": "en-US"}),
        timeout=30,
    )
    resp.raise_for_status()
    out = [
        {"code": r["iso_3166_1"], "name": r.get("english_name") or r["iso_3166_1"]}
        for r in resp.json().get("results", [])
    ]
    out.sort(key=lambda r: r["name"])
    return out
