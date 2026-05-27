# Clueless Clone

A clone of the semantic word-guessing game at lessgames.com/clueless. Hosted on AWS.

## Purpose
Crash course in AWS basics — targeting EC2 for the backend and S3 for static assets.

## Recent Progress And Technical Choices
- CPU-first inference stack:
	- `torch` is installed from the dedicated CPU wheel index (`https://download.pytorch.org/whl/cpu`) via `pyproject.toml`.
	- This avoids accidental CUDA/GPU builds in cloud environments where only CPU instances are used.
- Default embedding backend remains local and deterministic:
	- `sentence-transformers` with `BAAI/bge-small-en-v1.5`.
	- Model loads once and is reused for all requests.
- Runtime behavior improvements:
	- Startup warmup uses FastAPI lifespan to preload today's secret word embedding.
	- Guess scoring now uses an exponential curve (`round(exp(distance * 8) - 1)`) for better spread between close guesses.
- Persistence and deployment path are now production-oriented:
	- Storage is abstracted behind `storage.py` with local filesystem default and S3 when `USE_S3=true`.
	- Added `deploy/setup.sh` to bootstrap EC2 (system packages, uv, service, nginx reverse proxy).

## How It Works
1. Each day a new secret word is chosen deterministically (SHA-256 of the date) from `words.txt`, without replacement.
2. Players guess single words via a text input.
3. Each guess is embedded using `BAAI/bge-small-en-v1.5` and its cosine distance to the secret word is returned. Lower = closer.
4. Distances trend toward 0 as guesses improve. Reaching 0 wins the game.
5. Guesses and their distances are cached per-day in `cache/YYYY-MM-DD.json` so embeddings are never computed twice.

## Status
- [x] FastAPI backend with `/guess`, `/guesses`, `/status`, `/answer`, and `DELETE /cache` endpoints
- [x] `BAAI/bge-small-en-v1.5` embeddings via `sentence-transformers` (local default)
- [x] CPU-only PyTorch dependency source configured via uv index (`pytorch-cpu`)
- [x] Per-day JSON cache for already-seen words
- [x] Deterministic daily word selection with used-word tracking
- [x] Single-file vanilla HTML/CSS/JS frontend with heat-bar distance display
- [x] Pluggable storage layer — `USE_S3=true` switches all persistence to S3; local filesystem used by default
- [x] EC2 bootstrap script (`deploy/setup.sh`) with systemd + nginx wiring
- [ ] AWS deployment (EC2 + S3)
- [ ] Per-user session tracking
- [ ] Rate limiting

## Environment Variables
- `USE_S3` (`false` by default): store cache + used words in S3 instead of local files.
- `S3_BUCKET`: required when `USE_S3=true`.
- `AWS_DEFAULT_REGION`: S3 region (default `us-east-2`).
- `ALLOWED_ORIGINS`: comma-separated CORS origins (default `*`).

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

