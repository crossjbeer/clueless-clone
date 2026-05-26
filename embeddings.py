"""
embeddings.py — Embedding model loading and cosine distance calculation.

Default model: BAAI/bge-small-en-v1.5
  - Lightweight (~130 MB), strong semantic quality for single English words.
  - Downloaded once by sentence-transformers and cached locally.

OpenAI model: text-embedding-3-small (requires USE_OPENAI_EMBEDDING=true and OPENAI_API_KEY)
  - Calls the OpenAI Embeddings API instead of a local model.

Distance: cosine distance = 1 - cosine_similarity, range [0, 2].
  A distance of 0 means the words are identical; lower is always better.
"""

import os

import numpy as np
from dotenv import load_dotenv

load_dotenv()

_USE_OPENAI = os.getenv("USE_OPENAI_EMBEDDING", "false").lower() == "true"

# ── Local (sentence-transformers) backend ────────────────────────────────────

_LOCAL_MODEL_NAME = "BAAI/bge-small-en-v1.5"

try:
    from sentence_transformers import SentenceTransformer as _SentenceTransformer
    _local_model: "_SentenceTransformer | None" = None
except ImportError:
    _SentenceTransformer = None  # type: ignore[assignment,misc]
    _local_model = None


def _get_local_model() -> "_SentenceTransformer":
    global _local_model
    if _local_model is None:
        if _SentenceTransformer is None:
            raise RuntimeError("sentence-transformers is not installed")
        _local_model = _SentenceTransformer(_LOCAL_MODEL_NAME)
    return _local_model


def _embed_local(word: str) -> np.ndarray:
    model = _get_local_model()
    vector = model.encode(word, normalize_embeddings=True)
    return np.array(vector, dtype=np.float32)


# ── OpenAI backend ───────────────────────────────────────────────────────────

_OPENAI_MODEL = "text-embedding-3-small"
_openai_client = None


def _get_openai_client():
    global _openai_client
    if _openai_client is None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("openai package is not installed — run: uv add openai") from exc
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set in the environment or .env file")
        _openai_client = OpenAI(api_key=api_key)
    return _openai_client


def _embed_openai(word: str) -> np.ndarray:
    client = _get_openai_client()
    response = client.embeddings.create(model=_OPENAI_MODEL, input=word)
    vector = np.array(response.data[0].embedding, dtype=np.float32)
    # L2-normalise so cosine_distance() (which assumes unit vectors) is correct
    norm = np.linalg.norm(vector)
    if norm > 0:
        vector = vector / norm
    return vector


# ── Public API ───────────────────────────────────────────────────────────────

def embed(word: str) -> np.ndarray:
    """Return the L2-normalised embedding vector for *word*."""
    word = word.lower().strip()
    if _USE_OPENAI:
        return _embed_openai(word)
    return _embed_local(word)


def cosine_distance(a: np.ndarray, b: np.ndarray) -> float:
    """
    Cosine distance between two L2-normalised vectors.
    Both inputs are assumed to already be unit-length (produced by embed()).
    Result is in [0, 2]; 0 = identical direction.
    """
    similarity = float(np.dot(a, b))
    # Clamp to [-1, 1] to guard against floating-point drift
    similarity = max(-1.0, min(1.0, similarity))
    return round(1.0 - similarity, 6)
