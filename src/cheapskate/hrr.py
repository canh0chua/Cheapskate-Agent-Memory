"""
HRR (Holographic Reduced Representations) encoder.

Pure Python implementation using deterministic hash projection.
No external dependencies beyond standard library.
"""

import hashlib
import math
import struct
from typing import List, Union

import numpy as np


def _deterministic_hash(text: str, dim: int, seed: int = 0) -> np.ndarray:
    """Generate a deterministic pseudo-random vector from text."""
    # Hash the text + seed to get a seed for PRNG
    hasher = hashlib.sha256()
    hasher.update(f"{seed}:{text}".encode("utf-8"))
    hash_bytes = hasher.digest()

    # Use the hash to seed numpy's random generator
    rng = np.random.RandomState(struct.unpack("<I", hash_bytes[:4])[0])

    # Generate a random vector from the seeded RNG
    vec = rng.randn(dim).astype(np.float32)

    # Normalize to unit length
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec


def encode(text: str, dim: int = 128) -> np.ndarray:
    """
    Encode text into a fixed-dimensional HRR vector.

    Args:
        text: Input text to encode
        dim: Dimensionality of the output vector (default 128)

    Returns:
        Normalized numpy array of shape (dim,) with dtype float32
    """
    return _deterministic_hash(text, dim, seed=0)


def similarity(v1: np.ndarray, v2: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    if v1.shape != v2.shape:
        raise ValueError(f"Shape mismatch: {v1.shape} vs {v2.shape}")
    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return float(np.dot(v1, v2) / (norm1 * norm2))


def bulk_encode(texts: List[str], dim: int = 128) -> List[np.ndarray]:
    """Encode multiple texts efficiently."""
    return [encode(t, dim) for t in texts]


def pack_vector(vec: np.ndarray) -> bytes:
    """Pack numpy array to bytes for database storage."""
    return vec.tobytes()


def unpack_vector(data: bytes, dim: int = 128) -> np.ndarray:
    """Unpack bytes back to numpy array."""
    vec = np.frombuffer(data, dtype=np.float32)
    if vec.shape[0] != dim:
        raise ValueError(f"Expected {dim} dimensions, got {vec.shape[0]}")
    return vec