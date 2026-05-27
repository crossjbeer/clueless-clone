"""
embeddings.py — Embedding model loading and cosine distance calculation.

Default model: BAAI/bge-small-en-v1.5
  - Lightweight (~130 MB), strong semantic quality for single English words.
  - Downloaded once by sentence-transformers and cached locally.

Distance: cosine distance = 1 - cosine_similarity, range [0, 2].
  A distance of 0 means the words are identical; lower is always better.
"""

import numpy as np
from dotenv import load_dotenv

load_dotenv()

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

# ── Public API ───────────────────────────────────────────────────────────────

def embed(word: str) -> np.ndarray:
    """Return the L2-normalised embedding vector for *word*."""
    word = word.lower().strip()
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
