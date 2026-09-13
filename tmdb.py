"""Minimal TMDB client: fetch movie/tv details + watch providers in one call."""
import requests

from config import (
    MUBI_NAME_MATCH,
    MUBI_PROVIDER_ID,
    TMDB_API_KEY,
    TMDB_READ_TOKEN,
)

BASE = "https://api.themoviedb.org/3"

_session = requests.Session()
if TMDB_READ_TOKEN:
    _session.headers.update({"Authorization": f"Bearer {TMDB_READ_TOKEN}"})


def _params(extra: dict | None = None) -> dict:
    p = dict(extra or {})
    # v4 read token goes in the header; v3 key goes in the query string.
    if not TMDB_READ_TOKEN and TMDB_API_KEY:
        p["api_key"] = TMDB_API_KEY
    return p


def get_details_and_providers(tmdb_id: int, media_type: str, region: str) -> dict:
    """Return {poster_path, title, providers} where providers is the region's
    grouped watch-provider dict, e.g. {"flatrate":[{id,name}], "free":[...]}.
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

    region_data = (
        data.get("watch/providers", {}).get("results", {}).get(region, {})
    )
    providers = {}
    for kind in ("flatrate", "free", "ads", "rent", "buy"):
        entries = region_data.get(kind) or []
        if entries:
            providers[kind] = [
                {"id": e.get("provider_id"), "name": e.get("provider_name")}
                for e in entries
            ]
    return {"title": title, "poster_path": poster_path, "providers": providers}


def is_on_mubi(providers: dict) -> bool:
    """True if Mubi offers it via subscription (flatrate) or free tier."""
    for kind in ("flatrate", "free"):
        for e in providers.get(kind, []):
            name = (e.get("name") or "").lower()
            if e.get("id") == MUBI_PROVIDER_ID or MUBI_NAME_MATCH in name:
                return True
    return False
