"""HuggingFace E5 multilingual embedding provider."""
import logging
import threading
from typing import List, Any

from app.providers.base import EmbeddingProvider

logger = logging.getLogger(__name__)


class HuggingFaceE5Provider(EmbeddingProvider):
    """Embedding provider using intfloat/multilingual-e5-base model.

    Features:
    - 768-dimensional embeddings
    - Multilingual (Hindi, English, etc.)
    - L2-normalized vectors
    - Query/passage prefix support (e5 requirement)
    - GPU acceleration with CPU fallback
    - Lazy model loading
    """

    def __init__(self, model_name: str = "intfloat/multilingual-e5-base", batch_size: int = 64):
        """Initialize provider.

        Args:
            model_name: HuggingFace model identifier.
            batch_size: Batch size for embedding.
        """
        self.model_name = model_name
        self.batch_size = batch_size
        self._model: Any = None
        self._load_lock = threading.Lock()
        self._device = self._get_device()
        logger.info(f"E5Provider initialized: model={model_name}, device={self._device}")

    def _get_device(self) -> str:
        """Detect device (cuda or cpu) with lazy torch import."""
        try:
            import torch
            return "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            return "cpu"

    def _load_model(self) -> None:
        """Lazy-load the embedding model (once, even if called from several threads)."""
        if self._model is not None:
            return
        with self._load_lock:
            if self._model is not None:
                return
            try:
                from sentence_transformers import SentenceTransformer
                logger.info(f"Loading model {self.model_name} on {self._device}...")
                self._model = SentenceTransformer(self.model_name, device=self._device)
                logger.info(f"Model loaded. Output dimension: {self._model.get_sentence_embedding_dimension()}")
            except ImportError as e:
                raise RuntimeError(f"sentence-transformers not installed: {e}") from e

    def warm_up(self) -> None:
        """Load the model and run one query so the first real search is fast."""
        self.embed_queries(["warm up"])
        logger.info("Embedding model warmed up")

    @property
    def dim(self) -> int:
        return 768

    def embed_passages(self, texts: List[str]) -> List[List[float]]:
        """Embed passages with 'passage: ' prefix."""
        return self._embed_texts([f"passage: {text}" for text in texts])

    def embed_queries(self, texts: List[str]) -> List[List[float]]:
        """Embed queries with 'query: ' prefix."""
        return self._embed_texts([f"query: {text}" for text in texts])

    def _embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Embed texts in batches.

        Args:
            texts: List of (already-prefixed) texts to embed.

        Returns:
            List of normalized embeddings.
        """
        self._load_model()

        embeddings = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            try:
                batch_embeddings = self._model.encode(
                    batch,
                    convert_to_numpy=True,
                    normalize_embeddings=True,
                    show_progress_bar=False,
                )
                embeddings.extend(batch_embeddings.tolist())
            except RuntimeError as e:
                if "out of memory" in str(e).lower():
                    # Handle OOM: clear cache and retry with smaller batch
                    logger.warning(f"OOM on batch size {len(batch)}, clearing cache and retrying")
                    try:
                        import torch
                        torch.cuda.empty_cache()
                    except ImportError:
                        pass

                    # Recursively retry with smaller batches
                    if len(batch) == 1:
                        raise RuntimeError(f"Cannot embed single text (OOM): {batch[0][:100]}") from e

                    smaller_batch_size = max(1, len(batch) // 2)
                    batch_embeddings = self._embed_texts_batch(batch, smaller_batch_size)
                    embeddings.extend(batch_embeddings)
                else:
                    raise

        return embeddings

    def _embed_texts_batch(self, texts: List[str], batch_size: int) -> List[List[float]]:
        """Embed texts with a specific batch size (used in OOM retry)."""
        embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            batch_embeddings = self._model.encode(
                batch,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            embeddings.extend(batch_embeddings.tolist())
        return embeddings
