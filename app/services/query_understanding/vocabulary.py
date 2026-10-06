"""Live catalogue facet vocabulary for LLM-inferred search filters.

The allowed values are the distinct non-null values of each facet column among
currently available products, read from the database. They are cached per
process for `catalogue_facets_cache_seconds`, so a catalogue sync that adds a
new value (e.g. a new color) reaches the LLM within that window, without a
restart, while the request path normally does no extra query.

Only category/gender/color/season are listed: these are the only SearchFilter
fields an LLM could plausibly infer from free text. `availability` is never
inferable from query text and is intentionally excluded.
"""
import logging
import threading
import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.product import Product
from core.config import settings

logger = logging.getLogger(__name__)

FACET_COLUMNS = {
    "category": Product.category,
    "gender": Product.gender,
    "color": Product.color,
    "season": Product.season,
}

_lock = threading.Lock()
_cached: dict[str, list[str]] | None = None
_cached_at = 0.0


def load_catalogue_facets(session: Session) -> dict[str, list[str]]:
    """Query the distinct facet values of available products (uncached)."""
    facets = {}
    for name, column in FACET_COLUMNS.items():
        stmt = (
            select(column)
            .where(column.is_not(None), Product.availability == True)
            .distinct()
            .order_by(column)
        )
        facets[name] = list(session.execute(stmt).scalars())
    return facets


def get_catalogue_facets(session: Session) -> dict[str, list[str]]:
    """Return the facet vocabulary, refreshing it from the DB when the cache expires.

    If a refresh fails but an older copy exists, the older copy is returned so a
    transient DB hiccup doesn't drop query understanding.
    """
    global _cached, _cached_at
    with _lock:
        if _cached is not None and time.monotonic() - _cached_at < settings.catalogue_facets_cache_seconds:
            return _cached
        try:
            _cached = load_catalogue_facets(session)
            _cached_at = time.monotonic()
        except Exception as e:
            if _cached is None:
                raise
            logger.warning(f"Refreshing catalogue facets failed, using previous values: {e}")
        return _cached


def _reset_catalogue_facets_cache() -> None:
    """Test-only hook to clear the cached vocabulary between test cases."""
    global _cached, _cached_at
    with _lock:
        _cached = None
        _cached_at = 0.0
