"""Unit tests for content hashing."""

import hashlib

from app.services.ingestion.hashing import compute_content_hash


class TestComputeContentHash:
    """Test content hashing for deduplication."""

    def test_deterministic_same_input(self):
        text = "hello world"
        hash1 = compute_content_hash(text)
        hash2 = compute_content_hash(text)
        assert hash1 == hash2

    def test_different_input_different_hash(self):
        hash1 = compute_content_hash("text1")
        hash2 = compute_content_hash("text2")
        assert hash1 != hash2

    def test_sha256_format(self):
        result = compute_content_hash("test")
        # SHA256 hex digest is 64 characters
        assert len(result) == 64
        # Should be hex characters
        assert all(c in "0123456789abcdef" for c in result)

    def test_consistency_with_hashlib(self):
        text = "test content"
        expected = hashlib.sha256(text.encode()).hexdigest()
        assert compute_content_hash(text) == expected

    def test_case_sensitive(self):
        hash1 = compute_content_hash("Hello")
        hash2 = compute_content_hash("hello")
        assert hash1 != hash2

    def test_whitespace_matters(self):
        hash1 = compute_content_hash("hello world")
        hash2 = compute_content_hash("helloworld")
        assert hash1 != hash2

    def test_empty_string(self):
        result = compute_content_hash("")
        expected = hashlib.sha256(b"").hexdigest()
        assert result == expected

    def test_long_text(self):
        text = "x" * 10000
        result = compute_content_hash(text)
        assert len(result) == 64
