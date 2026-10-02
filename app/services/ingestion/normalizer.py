"""Text normalization for deterministic hashing and search."""

from typing import Optional


def normalize_text(text: Optional[str]) -> Optional[str]:
    """
    Normalize text for deterministic hashing and search.

    Performs:
    - Strip leading/trailing whitespace
    - Convert to lowercase
    - Collapse repeated whitespace into single spaces

    Args:
        text: Input text to normalize.

    Returns:
        Normalized text, or None if input is None or empty after normalization.
    """
    if not text:
        return None

    normalized = " ".join(str(text).lower().split())
    return normalized if normalized else None
