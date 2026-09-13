# Letterboxd Watchlist → Mubi filter

A small local web app that loads your public [Letterboxd](https://letterboxd.com)
watchlist and lets you filter it by streaming availability. It currently
highlights films **available on Mubi** in a chosen region (default: UK), using
[TMDB](https://www.themoviedb.org)'s watch-provider data.

The provider data is stored per-service, so extending to other streamers later
is easy.

## How it works

1. Scrapes every page of your public watchlist for film slugs + titles.
2. Resolves each film's TMDB id from its Letterboxd page.
3. Asks TMDB for the poster + watch providers for your region (one call per film).
4. Caches everything in a local SQLite file (`cache.db`) so re-runs are instant.
5. Serves a poster grid with a "Only on Mubi" toggle and a search box.

## Setup

```bash
cd letterboxd-watchlist
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env: paste your TMDB API Read Access Token (or v3 API key).
# Get one free at https://www.themoviedb.org/settings/api
```

`.env` also holds your Letterboxd username (`LETTERBOXD_USERNAME`) and the
region for availability (`REGION`, e.g. `GB`, `US`, `BR`, `PT`).

## Run

```bash
python app.py
```

Open http://127.0.0.1:5000. On first load it automatically scrapes the
watchlist and checks availability (progress bar shows status — for ~400 films
this takes a couple of minutes). Later loads are instant from cache; hit
**Refresh** to pick up watchlist changes and re-check availability.

## Notes

- Only the **public** watchlist is read; no Letterboxd login is used.
- Scraping is deliberately gentle (8 concurrent requests, real User-Agent).
- Mubi is matched by TMDB provider id (11) or any provider whose name contains
  "mubi", covering variants like "Mubi Amazon Channel".
