"""Tests for HRR (Holographic Reduced Representations) encoder."""

import numpy as np
import pytest

from cheapskate.hrr import encode, similarity, bulk_encode, pack_vector, unpack_vector


class TestHRREncode:
    """Tests for the encode function."""

    def test_encode_returns_normalized_vector(self):
        """Encoded vectors should be normalized (unit length)."""
        vec = encode("hello world")
        norm = np.linalg.norm(vec)
        assert np.isclose(norm, 1.0), f"Expected norm ~1.0, got {norm}"

    def test_encode_deterministic(self):
        """Same input should produce same vector."""
        vec1 = encode("test string")
        vec2 = encode("test string")
        np.testing.assert_array_equal(vec1, vec2)

    def test_encode_different_texts_different_vectors(self):
        """Different texts should produce different vectors."""
        vec1 = encode("hello")
        vec2 = encode("goodbye")
        similarity_score = similarity(vec1, vec2)
        # Should not be identical (similarity < 1)
        assert similarity_score < 0.99

    def test_encode_empty_string(self):
        """Empty string should produce a valid vector."""
        vec = encode("")
        assert vec.shape == (128,)
        assert np.isclose(np.linalg.norm(vec), 1.0)

    def test_encode_custom_dimension(self):
        """Should support custom dimensions."""
        vec = encode("test", dim=64)
        assert vec.shape == (64,)
        assert np.isclose(np.linalg.norm(vec), 1.0)


class TestHRRSimilarity:
    """Tests for the similarity function."""

    def test_identical_vectors_similarity_one(self):
        """Identical vectors should have similarity 1.0."""
        vec = encode("test")
        sim = similarity(vec, vec)
        assert np.isclose(sim, 1.0)

    def test_opposite_vectors_similarity_minus_one(self):
        """Opposite vectors should have similarity -1.0."""
        vec = encode("test")
        opposite = -vec
        sim = similarity(vec, opposite)
        assert np.isclose(sim, -1.0)

    def test_perpendicular_vectors_similarity_zero(self):
        """Orthogonal vectors should have similarity ~0."""
        # Two random normalized vectors are likely not exactly orthogonal
        # but we can construct orthogonal vectors
        vec1 = np.array([1, 0, 0], dtype=np.float32)
        vec2 = np.array([0, 1, 0], dtype=np.float32)
        sim = similarity(vec1, vec2)
        assert np.isclose(sim, 0.0)

    def test_symmetric(self):
        """Similarity should be symmetric."""
        vec1 = encode("hello")
        vec2 = encode("world")
        sim12 = similarity(vec1, vec2)
        sim21 = similarity(vec2, vec1)
        assert np.isclose(sim12, sim21)

    def test_similar_texts_higher_similarity(self):
        """Similar texts should have higher similarity than dissimilar ones."""
        text_a = "The quick brown fox jumps over the lazy dog"
        text_b = "A fast brown fox leaps over a sleepy dog"
        text_c = "Python programming is fun and educational"

        vec_a = encode(text_a)
        vec_b = encode(text_b)
        vec_c = encode(text_c)

        sim_ab = similarity(vec_a, vec_b)
        sim_ac = similarity(vec_a, vec_c)
        # Similar texts should have higher similarity than dissimilar
        assert sim_ab > sim_ac

    def test_shape_mismatch_raises(self):
        """Vectors with different shapes should raise ValueError."""
        vec1 = np.random.randn(64).astype(np.float32)
        vec2 = np.random.randn(128).astype(np.float32)
        with pytest.raises(ValueError, match="Shape mismatch"):
            similarity(vec1, vec2)


class TestBulkEncode:
    """Tests for bulk_encode function."""

    def test_bulk_encode_returns_list(self):
        """Should return a list of vectors."""
        texts = ["hello", "world", "test"]
        result = bulk_encode(texts)
        assert isinstance(result, list)
        assert len(result) == 3

    def test_bulk_encode_shapes(self):
        """Each vector should have correct shape."""
        texts = ["a", "b", "c"]
        result = bulk_encode(texts, dim=64)
        for vec in result:
            assert vec.shape == (64,)
            assert np.isclose(np.linalg.norm(vec), 1.0)

    def test_bulk_encode_deterministic(self):
        """Same input list should produce same output."""
        texts = ["hello", "world"]
        result1 = bulk_encode(texts)
        result2 = bulk_encode(texts)
        for v1, v2 in zip(result1, result2):
            np.testing.assert_array_equal(v1, v2)


class TestVectorPacking:
    """Tests for pack_vector and unpack_vector."""

    def test_pack_unpack_roundtrip(self):
        """Packed and unpacked vectors should be identical."""
        original = encode("test vector", dim=128)
        packed = pack_vector(original)
        unpacked = unpack_vector(packed, dim=128)
        np.testing.assert_array_almost_equal(original, unpacked)

    def test_pack_unpack_different_dims(self):
        """Should work with different dimensions."""
        for dim in [64, 128, 256]:
            vec = encode("test", dim=dim)
            packed = pack_vector(vec)
            unpacked = unpack_vector(packed, dim=dim)
            np.testing.assert_array_almost_equal(vec, unpacked)

    def test_unpack_wrong_dim_raises(self):
        """Unpacking with wrong dimension should raise."""
        vec = encode("test", dim=128)
        packed = pack_vector(vec)
        with pytest.raises(ValueError, match="Expected 64 dimensions"):
            unpack_vector(packed, dim=64)


class TestHRRProperties:
    """Tests for HRR mathematical properties."""

    def test_unit_norm_property(self):
        """Vectors should maintain unit norm across many samples."""
        for i in range(10):
            vec = encode(f"test string {i}")
            norm = np.linalg.norm(vec)
            assert np.isclose(norm, 1.0), f"Sample {i}: norm={norm}"

    def test_similarity_range(self):
        """Similarities should be in range [-1, 1]."""
        vecs = [encode(f"text {i}") for i in range(5)]
        for i in range(len(vecs)):
            for j in range(len(vecs)):
                sim = similarity(vecs[i], vecs[j])
                assert -1.0 <= sim <= 1.001  # floating-point tolerance
