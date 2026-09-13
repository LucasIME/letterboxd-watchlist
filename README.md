# Letterboxd Watchlist → Mubi filter

A small local web app that loads your public [Letterboxd](https://letterboxd.com)
watchlist and lets you filter it by streaming availability, using
[TMDB](https://www.themoviedb.org)'s watch-provider data.

Two dropdowns drive it:

- **Service** — Mubi, Netflix, and every other streamer that carries a film on
  your watchlist (the list is built dynamically from your own list). Plus
  "Any service" (available on anything) and "All films" (no filter).
- **Region** — any TMDB country; the ones where you actually have films
  available are grouped at the top. Defaults to the `REGION` in your `.env`.

TMDB returns every country's providers in a single request, so switching
service or region is instant — no re-fetching.

## How it works

1. Scrapes every page of your public watchlist for film slugs + titles.
2. Resolves each film's TMDB id from its Letterboxd page.
3. Asks TMDB for the poster + watch providers **for every region** (one call per film).
4. Caches everything in a local SQLite file (`cache.db`) so re-runs are instant.
5. Serves a poster grid with service + region dropdowns and a search box.

## Setup

This project uses [uv](https://docs.astral.sh/uv/). Dependencies are declared in
`pyproject.toml` and pinned in `uv.lock`.

```bash
cd letterboxd-watchlist
uv sync            # creates .venv and installs deps from the lockfile

cp .env.example .env
# Edit .env: paste your TMDB API Read Access Token (or v3 API key).
# Get one free at https://www.themoviedb.org/settings/api
```

`.env` also holds your Letterboxd username (`LETTERBOXD_USERNAME`) and the
region for availability (`REGION`, e.g. `GB`, `US`, `BR`, `PT`).

## Run

```bash
uv run app.py
```

Open http://127.0.0.1:5000. On first load it automatically scrapes the
watchlist and checks availability (progress bar shows status — for ~400 films
this takes a couple of minutes). Later loads are instant from cache; hit
**Refresh** to pick up watchlist changes and re-check availability.

## Notes

- Only the **public** watchlist is read; no Letterboxd login is used.
- Scraping is deliberately gentle (8 concurrent requests, real User-Agent).
- "Available" means subscription (flatrate), free, or ad-supported — not
  rent/buy. Provider variants (e.g. "MUBI" vs "MUBI Amazon Channel") appear as
  separate services so you can choose precisely.
- `REGION` / `DEFAULT_SERVICE_ID` only set the *initial* dropdown selection;
  you can switch to any service/region in the UI without re-running anything.
