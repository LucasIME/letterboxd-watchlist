"""SQLite cache for watchlist films and their TMDB / provider data.

One row per film (keyed by Letterboxd slug). Provider data is stored as JSON
so the UI can filter by any service later, not just Mubi.
"""
import json
import sqlite3
import threading
import time
from contextlib import contextmanager

from config import DB_PATH

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
                region          TEXT,
                providers_json  TEXT,         -- {"flatrate":[{id,name}], "free":[...], ...}
                on_mubi         INTEGER DEFAULT 0,
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
    region=None,
    providers: dict | None = None,
    on_mubi: bool = False,
    error: str | None = None,
) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE films SET
                tmdb_id=?, tmdb_type=?, poster_path=?, region=?,
                providers_json=?, on_mubi=?, error=?, enriched_at=?
            WHERE slug=?
            """,
            (
                tmdb_id,
                tmdb_type,
                poster_path,
                region,
                json.dumps(providers) if providers is not None else None,
                1 if on_mubi else 0,
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
        d["providers"] = json.loads(d["providers_json"]) if d["providers_json"] else {}
        d.pop("providers_json", None)
        d["on_mubi"] = bool(d["on_mubi"])
        out.append(d)
    return out


def counts() -> dict:
    with get_conn() as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM films WHERE in_watchlist=1"
        ).fetchone()[0]
        enriched = conn.execute(
            "SELECT COUNT(*) FROM films WHERE in_watchlist=1 AND enriched_at IS NOT NULL"
        ).fetchone()[0]
        on_mubi = conn.execute(
            "SELECT COUNT(*) FROM films WHERE in_watchlist=1 AND on_mubi=1"
        ).fetchone()[0]
    return {"total": total, "enriched": enriched, "on_mubi": on_mubi}
