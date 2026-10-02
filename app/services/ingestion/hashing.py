"""Content hashing for idempotent ingestion."""

import hashlib


def compute_content_hash(text: str) -> str:
    """
    Compute SHA256 hash of text content.

    Used to detect changes between ingestion runs.
    Same input always produces same hash (deterministic).

    Args:
        text: Text to hash.

    Returns:
        SHA256 hexadecimal digest (64 characters).
    """
    return hashlib.sha256(text.encode()).hexdigest()
