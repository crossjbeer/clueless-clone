"""
users.py — Simple username registry (no passwords).

Storage key: users.json
Value format: JSON array of username strings.

Max 6 users; usernames are 1–30 characters, lowercase letters/digits/
hyphens/underscores only.
"""

import re

import storage

_KEY = "users.json"
_MAX_USERS = 6
_USERNAME_RE = re.compile(r'^[a-z0-9_-]{1,30}$')


def _load() -> list[str]:
    data = storage.read_json(_KEY)
    return data if isinstance(data, list) else []


def _save(users: list[str]) -> None:
    storage.write_json(_KEY, users)


def list_users() -> list[str]:
    """Return all registered usernames."""
    return _load()


def user_exists(username: str) -> bool:
    """Return True if *username* is already registered."""
    return username.strip().lower() in _load()


def create_user(username: str) -> tuple[bool, str]:
    """
    Register a new username.
    Returns (True, "") on success or (False, reason) on failure.
    """
    username = username.strip().lower()
    if not _USERNAME_RE.match(username):
        return False, (
            "Username must be 1–30 characters: "
            "letters, digits, hyphens, or underscores only."
        )
    users = _load()
    if username in users:
        return False, "That username is already taken."
    if len(users) >= _MAX_USERS:
        return False, f"The game is full — maximum {_MAX_USERS} players reached."
    users.append(username)
    _save(users)
    return True, ""
