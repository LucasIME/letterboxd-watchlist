"""Configuration loaded from environment / .env file."""
import os

from dotenv import load_dotenv

load_dotenv()

TMDB_READ_TOKEN = os.getenv("TMDB_READ_TOKEN", "").strip()
TMDB_API_KEY = os.getenv("TMDB_API_KEY", "").strip()

LETTERBOXD_USERNAME = os.getenv("LETTERBOXD_USERNAME", "lucasime").strip()
REGION = os.getenv("REGION", "GB").strip().upper()

# Where the SQLite cache lives.
DB_PATH = os.path.join(os.path.dirname(__file__), "cache.db")

# Polite User-Agent for scraping Letterboxd.
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

# TMDB provider identity for Mubi. We match on id OR name to catch variants
# like "Mubi Amazon Channel".
MUBI_PROVIDER_ID = 11
MUBI_NAME_MATCH = "mubi"


def tmdb_configured() -> bool:
    return bool(TMDB_READ_TOKEN or TMDB_API_KEY)
