"""SQLite cache for watchlist films and their TMDB / provider data.

One row per film (keyed by Letterboxd slug). Watch-provider data is stored as
JSON for *all* regions at once, so filtering by region/service is a local
operation needing no further TMDB calls.
"""
import json
import sqlite3
import threading
import time
from contextlib import contextmanager

from config import DB_PATH

# Provider kinds that count as "available to watch on <service>".
AVAILABLE_KINDS = ("flatrate", "free", "ads")

_local = threading.local()


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


@contextmanager
def get_conn():
    """Thread-local connection (SQLite connections aren't shareable across threads)."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = _connect()
        _local.conn = conn
    yield conn


def init_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS films (
                slug            TEXT PRIMARY KEY,
                title           TEXT,
                year            INTEGER,
                position        INTEGER,      -- order in the watchlist
                in_watchlist    INTEGER DEFAULT 1,
                tmdb_id         INTEGER,
                tmdb_type       TEXT,
                poster_path     TEXT,
                providers_json  TEXT,         -- {"GB": {"flatrate":[{id,name}]}, ...}
                error           TEXT,
                enriched_at     REAL
            )
            """
        )
        conn.commit()


def upsert_watchlist_film(slug: str, title: str, year, position: int) -> None:
    """Insert or update the basic watchlist entry, preserving enrichment data."""
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO films (slug, title, year, position, in_watchlist)
            VALUES (?, ?, ?, ?, 1)
            ON CONFLICT(slug) DO UPDATE SET
                title=excluded.title,
                year=excluded.year,
                position=excluded.position,
                in_watchlist=1
            """,
            (slug, title, year, position),
        )
        conn.commit()


def mark_absent_except(slugs) -> None:
    """Flag films no longer in the watchlist (removed since last scrape)."""
    with get_conn() as conn:
        conn.execute("UPDATE films SET in_watchlist=0")
        conn.executemany(
            "UPDATE films SET in_watchlist=1 WHERE slug=?",
            [(s,) for s in slugs],
        )
        conn.commit()


def films_needing_enrichment(max_age_seconds: float | None = None):
    """Slugs of in-watchlist films that have never been enriched (or are stale)."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT slug, enriched_at FROM films WHERE in_watchlist=1"
        ).fetchall()
    now = time.time()
    out = []
    for r in rows:
        if r["enriched_at"] is None:
            out.append(r["slug"])
        elif max_age_seconds is not None and now - r["enriched_at"] > max_age_seconds:
            out.append(r["slug"])
    return out


def save_enrichment(
    slug: str,
    *,
    tmdb_id=None,
    tmdb_type=None,
    poster_path=None,
    providers_by_region: dict | None = None,
    error: str | None = None,
) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE films SET
                tmdb_id=?, tmdb_type=?, poster_path=?,
                providers_json=?, error=?, enriched_at=?
            WHERE slug=?
            """,
            (
                tmdb_id,
                tmdb_type,
                poster_path,
                json.dumps(providers_by_region) if providers_by_region is not None else None,
                error,
                time.time(),
                slug,
            ),
        )
        conn.commit()


def all_films():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM films WHERE in_watchlist=1 ORDER BY position ASC"
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["providers_by_region"] = (
            json.loads(d["providers_json"]) if d["providers_json"] else {}
        )
        d.pop("providers_json", None)
        out.append(d)
    return out


# --- filtering / options helpers -------------------------------------------

def region_providers(film: dict, region: str) -> list[dict]:
    """The [{id, name}] available (subscription/free/ads) for a film in a region."""
    region_data = film.get("providers_by_region", {}).get(region, {})
    seen, out = set(), []
    for kind in AVAILABLE_KINDS:
        for p in region_data.get(kind, []):
            if p["id"] not in seen:
                seen.add(p["id"])
                out.append(p)
    return out


def film_available(film: dict, region: str, service_id) -> bool:
    """True if the film is available in `region`; if service_id given, on that service."""
    provs = region_providers(film, region)
    if service_id in (None, "", "any"):
        return bool(provs)
    return any(p["id"] == int(service_id) for p in provs)


def available_regions(films) -> set:
    """Region codes where at least one watchlist film is available."""
    regions = set()
    for f in films:
        for region, data in f.get("providers_by_region", {}).items():
            if any(data.get(k) for k in AVAILABLE_KINDS):
                regions.add(region)
    return regions


def services_for_region(films, region: str) -> list[dict]:
    """Distinct [{id, name}] services offering any watchlist film in `region`."""
    by_id = {}
    for f in films:
        for p in region_providers(f, region):
            by_id.setdefault(p["id"], p["name"])
    out = [{"id": pid, "name": name} for pid, name in by_id.items()]
    out.sort(key=lambda s: s["name"].lower())
    return out


def counts() -> dict:
    with get_conn() as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM films WHERE in_watchlist=1"
        ).fetchone()[0]
        enriched = conn.execute(
            "SELECT COUNT(*) FROM films WHERE in_watchlist=1 AND enriched_at IS NOT NULL"
        ).fetchone()[0]
    return {"total": total, "enriched": enriched}
