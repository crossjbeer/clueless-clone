"""
cache.py — Per-day cache of guessed words and their cosine distances.

Storage key: cache/YYYY-MM-DD.json  (local model)
             cache/openai/YYYY-MM-DD.json  (OpenAI embedding model)
Value format: JSON object mapping lowercase word strings to float distances.

Example:  cache/2026-05-21.json
  {"river": 0.312, "ocean": 0.189, "lake": 0.401}

Storage backend is determined by the USE_S3 env var (see storage.py).
Cache namespace is determined by the USE_OPENAI_EMBEDDING env var.
"""

import os
from datetime import date

import storage

_CACHE_PREFIX = "cache/openai" if os.getenv("USE_OPENAI_EMBEDDING", "false").lower() == "true" else "cache"


def _key(day: date) -> str:
    return f"{_CACHE_PREFIX}/{day.isoformat()}.json"


def load_cache(day: date | None = None) -> dict[str, float]:
    """Return today's word → distance mapping (empty dict if none yet)."""
    if day is None:
        day = date.today()
    data = storage.read_json(_key(day))
    return data if data is not None else {}


def save_cache(cache: dict[str, float], day: date | None = None) -> None:
    """Persist the word → distance mapping for *day*."""
    if day is None:
        day = date.today()
    storage.write_json(_key(day), cache)


def get_cached_distance(word: str, day: date | None = None) -> float | None:
    """Return the cached distance for *word* today, or None if not yet seen."""
    return load_cache(day).get(word.lower().strip())


def store_distance(word: str, distance: float, day: date | None = None) -> None:
    """Add or update the cached distance for *word* today."""
    cache = load_cache(day)
    cache[word.lower().strip()] = distance
    save_cache(cache, day)

