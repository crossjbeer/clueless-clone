"""
cache.py — Per-day, per-user cache of guessed words and their cosine distances.

Storage key: cache/YYYY-MM-DD_<user_id>.json
Value format: JSON object mapping lowercase word strings to float distances.

Example:  cache/2026-05-21_alice.json
  {"river": 0.312, "ocean": 0.189, "lake": 0.401}

Storage backend is determined by the USE_S3 env var (see storage.py).
"""

from datetime import date

import storage

_CACHE_PREFIX = "cache"


def _key(day: date, user_id: str) -> str:
    return f"{_CACHE_PREFIX}/{day.isoformat()}_{user_id}.json"


def load_cache(day: date | None = None, user_id: str = "default") -> dict[str, float]:
    """Return today's word → distance mapping for *user_id* (empty dict if none yet)."""
    if day is None:
        day = date.today()
    data = storage.read_json(_key(day, user_id))
    return data if data is not None else {}


def save_cache(cache: dict[str, float], day: date | None = None, user_id: str = "default") -> None:
    """Persist the word → distance mapping for *day* and *user_id*."""
    if day is None:
        day = date.today()
    storage.write_json(_key(day, user_id), cache)


def get_cached_distance(word: str, day: date | None = None, user_id: str = "default") -> float | None:
    """Return the cached distance for *word* today, or None if not yet seen."""
    return load_cache(day, user_id).get(word.lower().strip())


def store_distance(word: str, distance: float, day: date | None = None, user_id: str = "default") -> None:
    """Add or update the cached distance for *word* today."""
    cache = load_cache(day, user_id)
    cache[word.lower().strip()] = distance
    save_cache(cache, day, user_id)

