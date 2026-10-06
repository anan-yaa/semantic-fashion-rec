"""Deterministic fake embedding provider for testing."""
import hashlib

import numpy as np

from app.providers.base import EmbeddingProvider


class FakeEmbeddingProvider(EmbeddingProvider):
    """Deterministic embedding provider that generates 768-dim vectors from text hashes.

    Used for integration tests to avoid loading real models.
    Produces the same embedding for the same text every time, and embeddings are L2-normalized.
    """

    @property
    def dim(self) -> int:
        return 768

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        """Embed passages (no prefix needed for fake)."""
        return self._embed_deterministic(texts)

    def embed_queries(self, texts: list[str]) -> list[list[float]]:
        """Embed queries (no prefix needed for fake)."""
        return self._embed_deterministic(texts)

    def _embed_deterministic(self, texts: list[str]) -> list[list[float]]:
        """Generate deterministic, normalized embeddings from text hashes."""
        embeddings = []
        for text in texts:
            # Hash the text to seed the RNG
            hash_bytes = hashlib.sha256(text.encode('utf-8')).digest()
            seed = int.from_bytes(hash_bytes[:8], 'big') % (2**32)

            # Generate pseudo-random vector
            rng = np.random.RandomState(seed)
            vec = rng.randn(self.dim).astype(np.float32)

            # L2-normalize to unit length (like e5 does)
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm

            embeddings.append(vec.tolist())

        return embeddings
