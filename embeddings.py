"""
embeddings.py — Embedding model loading and cosine distance calculation.

Model: BAAI/bge-small-en-v1.5
  - Lightweight (~130 MB), strong semantic quality for single English words.
  - Downloaded once by sentence-transformers and cached locally.

Distance: cosine distance = 1 - cosine_similarity, range [0, 2].
  A distance of 0 means the words are identical; lower is always better.
"""

import numpy as np
from sentence_transformers import SentenceTransformer

_MODEL_NAME = "BAAI/bge-small-en-v1.5"
_model: SentenceTransformer | None = None


def get_model() -> SentenceTransformer:
    """Return the (lazily loaded) singleton embedding model."""
    global _model
    if _model is None:
        _model = SentenceTransformer(_MODEL_NAME)
    return _model


def embed(word: str) -> np.ndarray:
    """Return the L2-normalised embedding vector for *word*."""
    model = get_model()
    vector = model.encode(word.lower().strip(), normalize_embeddings=True)
    return np.array(vector, dtype=np.float32)


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
