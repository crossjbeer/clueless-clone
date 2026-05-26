# Clueless Clone

A clone of the semantic word-guessing game at lessgames.com/clueless. Hosted on AWS.

## Purpose
Crash course in AWS basics — targeting EC2 for the backend and S3 for static assets.

## How It Works
1. Each day a new secret word is chosen deterministically (SHA-256 of the date) from `words.txt`, without replacement.
2. Players guess single words via a text input.
3. Each guess is embedded using `BAAI/bge-small-en-v1.5` and its cosine distance to the secret word is returned. Lower = closer.
4. Distances trend toward 0 as guesses improve. Reaching 0 wins the game.
5. Guesses and their distances are cached per-day in `cache/YYYY-MM-DD.json` so embeddings are never computed twice.

## Status
- [x] FastAPI backend with `/guess`, `/guesses`, `/status`, `/answer`, and `DELETE /cache` endpoints
- [x] `BAAI/bge-small-en-v1.5` embeddings via `sentence-transformers`
- [x] Per-day JSON cache for already-seen words
- [x] Deterministic daily word selection with used-word tracking
- [x] Single-file vanilla HTML/CSS/JS frontend with heat-bar distance display
- [x] Pluggable storage layer — `USE_S3=true` switches all persistence to S3; local filesystem used by default
- [ ] AWS deployment (EC2 + S3)
- [ ] Per-user session tracking
- [ ] Rate limiting

## Running Locally

```bash
uv sync
uv run uvicorn main:app --reload
```

Open http://127.0.0.1:8000. Interactive API docs at http://127.0.0.1:8000/docs.

## Project Structure

```
main.py        # FastAPI app
words.py       # Daily word selection
embeddings.py  # Model loading and cosine distance
cache.py       # Per-day guess cache
storage.py     # Storage abstraction (local filesystem or S3)
words.txt      # Comma-separated word list
index.html     # Game UI (single file)
pyproject.toml # Dependencies (managed by uv)
.env.example   # Environment variable template
cache/         # Auto-created locally; one JSON file per day
```

