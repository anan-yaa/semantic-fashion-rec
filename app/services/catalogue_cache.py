"""Per-process TTL cache for vocabularies read from the product catalogue."""
import logging
import threading
import time
from collections.abc import Callable
from typing import Generic, TypeVar

from sqlalchemy.orm import Session

from core.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CatalogueCache(Generic[T]):
    """Caches `loader(session)` for `catalogue_facets_cache_seconds`.

    A catalogue sync that adds new values is picked up within that window
    without a restart. If a refresh fails but an older copy exists, the older
    copy is returned so a transient DB error doesn't break the request.
    """

    def __init__(self, loader: Callable[[Session], T]):
        self._loader = loader
        self._lock = threading.Lock()
        self._value: T | None = None
        self._loaded_at = 0.0

    def get(self, session: Session) -> T:
        with self._lock:
            fresh = time.monotonic() - self._loaded_at < settings.catalogue_facets_cache_seconds
            if self._value is not None and fresh:
                return self._value
            try:
                self._value = self._loader(session)
                self._loaded_at = time.monotonic()
            except Exception as e:
                if self._value is None:
                    raise
                logger.warning(f"Refreshing catalogue cache failed, using previous values: {e}")
            return self._value

    def reset(self) -> None:
        with self._lock:
            self._value = None
            self._loaded_at = 0.0
