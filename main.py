"""
main.py — Clueless Clone API

Endpoints
---------
POST /guess
    Body: { "word": "river" }
    Returns a similarity score (0–100) between the guessed word and today's
    secret word.  A score of 100 means the word is correct.

GET /guesses
    Returns all words guessed today (by any user) and their distances,
    sorted from closest to furthest.

GET /status
    Returns non-sensitive game metadata: today's date, total guesses so far,
    and whether the secret word has been found today.
"""

from contextlib import asynccontextmanager
from datetime import date
import math
import os

import re

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, field_validator

from cache import get_cached_distance, load_cache, save_cache, store_distance
from embeddings import embed
from users import create_user, list_users, user_exists
from words import get_daily_word

# ---------------------------------------------------------------------------
# App state — loaded once at startup
# ---------------------------------------------------------------------------

class AppState:
    secret_word: str = ""
    secret_embedding: np.ndarray | None = None
    loaded_for: date | None = None


state = AppState()


def refresh_daily_state() -> None:
    """(Re-)load the secret word and its embedding if the day has changed."""
    today = date.today()
    if state.loaded_for == today:
        return
    state.secret_word = get_daily_word(today)
    state.secret_embedding = embed(state.secret_word)
    state.loaded_for = today


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Eagerly load the model and today's secret word on startup so the first
    # request is not penalised by the model download / warm-up time.
    refresh_daily_state()
    yield


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Clueless Clone API",
    description="Guess the secret word by semantic similarity.",
    version="0.1.0",
    lifespan=lifespan,
)

_raw_origins = os.getenv("ALLOWED_ORIGINS", "*")
_allow_origins: list[str] = [o.strip() for o in _raw_origins.split(",")] if _raw_origins != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

_USER_ID_RE = re.compile(r'^[a-z0-9_-]{1,30}$')


def _validate_user_id(user_id: str) -> str:
    """Normalise and validate a user_id string; raises HTTPException on failure."""
    user_id = user_id.strip().lower()
    if not _USER_ID_RE.match(user_id):
        raise HTTPException(
            status_code=422,
            detail="user_id must be 1–30 alphanumeric/underscore/hyphen characters.",
        )
    return user_id


class GuessRequest(BaseModel):
    word: str
    user_id: str

    @field_validator("word")
    @classmethod
    def word_must_be_single_token(cls, v: str) -> str:
        v = v.strip().lower()
        if not v:
            raise ValueError("word must not be empty")
        if len(v.split()) > 1:
            raise ValueError("only single words are accepted")
        if len(v) > 50:
            raise ValueError("word is too long")
        return v

    @field_validator("user_id")
    @classmethod
    def user_id_must_be_valid(cls, v: str) -> str:
        v = v.strip().lower()
        if not _USER_ID_RE.match(v):
            raise ValueError("user_id must be 1–30 alphanumeric/underscore/hyphen characters")
        return v


def score_from_distance(distance: float) -> int:
    """Convert cosine distance to an exponential score (0 = exact match, higher = further).
    Formula: round(exp(distance * 8) - 1)
    Gives fine-grained resolution near 0 and rapidly rising scores for cold guesses.
    """
    return round(math.exp(distance * 8) - 1)


class GuessResponse(BaseModel):
    word: str
    score: int
    is_correct: bool


class GuessEntry(BaseModel):
    word: str
    score: int


class GuessesResponse(BaseModel):
    date: str
    guesses: list[GuessEntry]


class StatusResponse(BaseModel):
    date: str
    total_guesses: int
    solved: bool


class UsersResponse(BaseModel):
    users: list[str]


class CreateUserRequest(BaseModel):
    username: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
def index() -> FileResponse:
    return FileResponse("index.html")


@app.get("/users", response_model=UsersResponse)
def get_users() -> UsersResponse:
    """Return all registered usernames."""
    return UsersResponse(users=list_users())


@app.post("/users", status_code=201)
def register_user(request: CreateUserRequest):
    """Register a new username. 409 if the name is taken or the game is full."""
    ok, reason = create_user(request.username)
    if not ok:
        raise HTTPException(status_code=409, detail=reason)
    return {"username": request.username.strip().lower()}


@app.post("/guess", response_model=GuessResponse)
def guess(request: GuessRequest) -> GuessResponse:
    """Submit a guess. Returns the cosine distance to today's secret word."""
    refresh_daily_state()

    word = request.word
    user_id = request.user_id

    if not user_exists(user_id):
        raise HTTPException(status_code=403, detail="Unknown user. Please sign in or create an account.")

    # Return cached result immediately if we've seen this word today
    cached = get_cached_distance(word, user_id=user_id)
    if cached is not None:
        return GuessResponse(word=word, score=score_from_distance(cached), is_correct=cached == 0.0)

    # Compute distance and cache it
    guess_embedding = embed(word)
    from embeddings import cosine_distance
    distance = cosine_distance(state.secret_embedding, guess_embedding)

    # Exact match: treat tiny floating-point residuals as zero
    if word == state.secret_word:
        distance = 0.0

    store_distance(word, distance, user_id=user_id)
    return GuessResponse(word=word, score=score_from_distance(distance), is_correct=distance == 0.0)


@app.get("/guesses", response_model=GuessesResponse)
def guesses(user_id: str = "default") -> GuessesResponse:
    """Return all words guessed today by *user_id*, sorted by distance (closest first)."""
    refresh_daily_state()
    user_id = _validate_user_id(user_id)
    today = date.today()
    cache = load_cache(today, user_id=user_id)
    sorted_entries = sorted(
        [GuessEntry(word=w, score=score_from_distance(d)) for w, d in cache.items()],
        key=lambda e: e.score,
    )
    return GuessesResponse(date=today.isoformat(), guesses=sorted_entries)


class AnswerResponse(BaseModel):
    word: str


@app.get("/answer", response_model=AnswerResponse)
def answer() -> AnswerResponse:
    """Reveal today's secret word (spoiler endpoint)."""
    refresh_daily_state()
    return AnswerResponse(word=state.secret_word)


@app.delete("/cache", status_code=204)
def purge_cache(user_id: str = "default") -> None:
    """Delete all cached guesses for today for *user_id*. Useful for testing."""
    user_id = _validate_user_id(user_id)
    save_cache({}, date.today(), user_id=user_id)


@app.get("/status", response_model=StatusResponse)
def status(user_id: str = "default") -> StatusResponse:
    """Return non-sensitive game metadata for today for *user_id*."""
    refresh_daily_state()
    user_id = _validate_user_id(user_id)
    today = date.today()
    cache = load_cache(today, user_id=user_id)
    solved = any(d == 0.0 for d in cache.values())
    return StatusResponse(
        date=today.isoformat(),
        total_guesses=len(cache),
        solved=solved,
    )
