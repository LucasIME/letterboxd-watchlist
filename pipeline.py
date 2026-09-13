"""Orchestrates: scrape watchlist -> resolve TMDB -> fetch providers.

Runs in a background thread so the web UI stays responsive, and reports
progress via a shared, thread-safe state object.
"""
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import db
import letterboxd
import tmdb
from config import LETTERBOXD_USERNAME

# How many films to enrich concurrently. Kept modest to stay polite to
# Letterboxd (one film-page fetch each); TMDB tolerates far more.
MAX_WORKERS = 8


class RefreshState:
    def __init__(self):
        self._lock = threading.Lock()
        self.running = False
        self.phase = "idle"          # idle | scraping | enriching | done | error
        self.total = 0
        self.done = 0
        self.message = ""
        self.finished_at = None

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "running": self.running,
                "phase": self.phase,
                "total": self.total,
                "done": self.done,
                "message": self.message,
                "finished_at": self.finished_at,
            }

    def update(self, **kwargs):
        with self._lock:
            for k, v in kwargs.items():
                setattr(self, k, v)


state = RefreshState()


def _enrich_one(slug: str):
    try:
        tmdb_id, tmdb_type = letterboxd.resolve_tmdb(slug)
        if not tmdb_id:
            db.save_enrichment(slug, error="No TMDB id on Letterboxd page")
            return
        details = tmdb.get_details_and_providers(tmdb_id, tmdb_type)
        db.save_enrichment(
            slug,
            tmdb_id=tmdb_id,
            tmdb_type=tmdb_type,
            poster_path=details["poster_path"],
            providers_by_region=details["providers_by_region"],
        )
    except Exception as exc:  # noqa: BLE001 - record and continue
        db.save_enrichment(slug, error=f"{type(exc).__name__}: {exc}")


def _run(force: bool):
    try:
        db.init_db()
        state.update(
            running=True, phase="scraping", done=0, total=0,
            message="Fetching watchlist from Letterboxd…", finished_at=None,
        )

        slugs = []
        for pos, film in enumerate(letterboxd.fetch_watchlist(LETTERBOXD_USERNAME)):
            db.upsert_watchlist_film(
                film["slug"], film["title"], film["year"], pos
            )
            slugs.append(film["slug"])
            state.update(total=len(slugs), message=f"Found {len(slugs)} films…")
        db.mark_absent_except(slugs)

        # Which films still need TMDB/provider data. force -> re-enrich all.
        to_enrich = slugs if force else db.films_needing_enrichment()
        state.update(
            phase="enriching",
            total=len(to_enrich),
            done=0,
            message=f"Checking availability for {len(to_enrich)} films…",
        )

        if to_enrich:
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
                futures = {pool.submit(_enrich_one, s): s for s in to_enrich}
                done = 0
                for _ in as_completed(futures):
                    done += 1
                    state.update(done=done)

        state.update(
            phase="done",
            running=False,
            message="Up to date.",
            finished_at=time.time(),
        )
    except Exception as exc:  # noqa: BLE001
        state.update(
            phase="error",
            running=False,
            message=f"{type(exc).__name__}: {exc}",
            finished_at=time.time(),
        )


def start_refresh(force: bool = False) -> bool:
    """Kick off a background refresh. Returns False if one is already running."""
    if state.running:
        return False
    state.update(running=True)
    threading.Thread(target=_run, args=(force,), daemon=True).start()
    return True
