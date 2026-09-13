"""Scrape a public Letterboxd watchlist and resolve TMDB ids from film pages."""
import re

import requests
from bs4 import BeautifulSoup

from config import USER_AGENT

BASE = "https://letterboxd.com"

_session = requests.Session()
_session.headers.update({"User-Agent": USER_AGENT})

# "Wings of Desire (1987)" -> ("Wings of Desire", 1987)
_NAME_YEAR = re.compile(r"^(.*?)\s*\((\d{4})\)\s*$")


def _split_name_year(item_name: str):
    m = _NAME_YEAR.match(item_name or "")
    if m:
        return m.group(1).strip(), int(m.group(2))
    return (item_name or "").strip(), None


def fetch_watchlist(username: str):
    """Yield dicts {slug, title, year} for every film in the watchlist, in order.

    Walks pages until one returns no films.
    """
    seen = set()
    page = 1
    while True:
        url = f"{BASE}/{username}/watchlist/page/{page}/"
        resp = _session.get(url, timeout=30)
        if resp.status_code == 404:
            break
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        posters = soup.select("[data-target-link]")
        found = 0
        for el in posters:
            link = el.get("data-target-link", "")
            m = re.match(r"^/film/([^/]+)/?$", link)
            if not m:
                continue
            slug = m.group(1)
            if slug in seen:
                continue
            seen.add(slug)
            title, year = _split_name_year(el.get("data-item-name", ""))
            found += 1
            yield {"slug": slug, "title": title, "year": year}

        if found == 0:
            break
        page += 1


_TMDB_ID = re.compile(r'data-tmdb-id="(\d+)"')
_TMDB_TYPE = re.compile(r'data-tmdb-type="([a-z]+)"')


def resolve_tmdb(slug: str):
    """Return (tmdb_id:int, tmdb_type:str) for a film slug, or (None, None)."""
    url = f"{BASE}/film/{slug}/"
    resp = _session.get(url, timeout=30)
    resp.raise_for_status()
    html = resp.text
    id_m = _TMDB_ID.search(html)
    type_m = _TMDB_TYPE.search(html)
    if not id_m:
        return None, None
    return int(id_m.group(1)), (type_m.group(1) if type_m else "movie")
