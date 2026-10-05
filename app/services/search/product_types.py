"""Detect catalogue product types (articleType, e.g. "Jackets") named in a query.

When a query names a product type, the shopper wants that type: for "black
leather jacket for men" a men's black jacket is a better answer than a men's
black leather wallet, even though both match three of the four ideas in the
query. Embedding similarity alone gets this wrong (it weighs "black leather"
heavily), so hybrid search restricts results to the named type.

Matching uses PostgreSQL's English stemming, the same as keyword search, against
the article types of available products read from the database. A type matches
when every one of its stemmed words appears in the query: "jacket" matches
"Jackets", "formal shoes" matches "Formal Shoes", but "shoes" alone matches
neither "Casual Shoes" nor "Formal Shoes".

Only the part of the query before the first relational word (for/to/with/
under/...) is used, because what follows describes context, not the item
wanted: "warm layer to wear under a jacket" is not asking for a jacket, and
"shoes to go with a red dress" is not asking for a dress.
"""
import re
from typing import Dict, FrozenSet, List

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.product import Product
from app.services.catalogue_cache import CatalogueCache

ARTICLE_TYPE = Product.attributes["articleType"].as_string()

# "t-shirt" -> "tshirt", so it matches "Tshirts" rather than "Shirts".
_HYPHENATED = re.compile(r"(\w)-(\w)")
_CONTEXT_START = re.compile(
    r"\b(?:for|to|with|under|over|beneath|underneath|match|matching)\b", re.IGNORECASE
)


def load_article_type_lexemes(session: Session) -> Dict[str, FrozenSet[str]]:
    """Map each available product's article type to its stemmed words."""
    stmt = (
        select(ARTICLE_TYPE, func.tsvector_to_array(func.to_tsvector("english", ARTICLE_TYPE)))
        .where(ARTICLE_TYPE.is_not(None), Product.availability == True)  # noqa: E712
        .distinct()
    )
    return {name: frozenset(lexemes) for name, lexemes in session.execute(stmt) if lexemes}


_cache = CatalogueCache(load_article_type_lexemes)


def detect_article_types(session: Session, query_text: str) -> List[str]:
    """Return the catalogue article types named in the query (PostgreSQL only)."""
    if session.bind.dialect.name != "postgresql":
        return []

    type_lexemes = _cache.get(session)
    item_phrase = _CONTEXT_START.split(query_text, maxsplit=1)[0]
    text = _HYPHENATED.sub(r"\1\2", item_phrase)
    if not text.strip():
        return []
    query_lexemes = set(
        session.execute(select(func.tsvector_to_array(func.to_tsvector("english", text)))).scalar() or []
    )
    return sorted(name for name, lexemes in type_lexemes.items() if lexemes <= query_lexemes)


def _reset_article_type_cache() -> None:
    """Test-only hook to clear the cached article types between test cases."""
    _cache.reset()
