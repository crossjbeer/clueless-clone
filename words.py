"""
words.py — Daily word selection.

Words are stored as a comma-separated list in words.txt (always local —
it ships with the code and is read-only).

A separate used_words.txt tracks which words have already been the daily word,
ensuring no repeats until the list is exhausted (then it resets).
This file is managed via storage.py so it can live in S3 in production.

The daily word is determined deterministically by hashing today's date so that
every server instance agrees on the same word without needing shared state.
"""

import hashlib
from datetime import date
from pathlib import Path

import storage

WORDS_FILE = Path(__file__).parent / "words.txt"
_USED_KEY = "used_words.txt"


def _load_all_words() -> list[str]:
    text = WORDS_FILE.read_text(encoding="utf-8").strip()
    return [w.strip().lower() for w in text.split(",") if w.strip()]


def _load_used_words() -> list[str]:
    text = storage.read_text(_USED_KEY)
    if not text or not text.strip():
        return []
    return [w.strip().lower() for w in text.split(",") if w.strip()]


def _save_used_words(used: list[str]) -> None:
    storage.write_text(_USED_KEY, ",".join(used))


def get_daily_word(today: date | None = None) -> str:
    """
    Return the secret word for *today*.

    The word is chosen by using today's ISO date as a seed to pick
    deterministically from the remaining (unused) words.  Once all words have
    been used, the used list resets.
    """
    if today is None:
        today = date.today()

    all_words = _load_all_words()
    used = _load_used_words()

    available = [w for w in all_words if w not in used]
    if not available:
        # Full reset — start over
        used = []
        _save_used_words(used)
        available = list(all_words)

    # Deterministic selection: hash(date) mod len(available)
    date_bytes = today.isoformat().encode()
    index = int(hashlib.sha256(date_bytes).hexdigest(), 16) % len(available)
    word = available[index]

    # Record as used if not already present (guards against multiple calls)
    if word not in used:
        used.append(word)
        _save_used_words(used)

    return word
