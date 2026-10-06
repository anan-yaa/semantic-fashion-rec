"""Outfit builder: one hybrid search per outfit slot, restricted to that slot's product group.

The slots are a fixed template over the catalogue's own subcategories, not
something an LLM invents: a 1B model can't reliably split "outfit for the
beach" into parts, but it doesn't need to. The full query is searched inside
each slot, so the occasion decides which footwear or accessory ranks first.
"""
import time
from collections import Counter
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.models.product import Product
from app.providers.base import EmbeddingProvider
from app.schemas.search import SearchFilter, SearchMethod
from app.services.query_understanding import merge_filters
from app.services.search import search_hybrid


@dataclass(frozen=True)
class Slot:
    key: str
    label: str
    category: str | None = None
    subcategories: tuple[str, ...] | None = None


OUTFIT_SLOTS = (
    Slot("top", "Top", subcategories=("Topwear",)),
    Slot("bottom", "Bottom", subcategories=("Bottomwear",)),
    Slot("footwear", "Footwear", category="Footwear"),
    Slot("accessory", "Accessory", subcategories=("Bags", "Watches", "Eyewear", "Jewellery")),
)

# Genders that describe who wears the outfit; "Unisex" says nothing about it.
_WEARER_GENDERS = ("Men", "Women", "Boys", "Girls")
# How many top results of the first slot vote on the outfit's gender.
_GENDER_VOTERS = 10
# The catalogue lists some products twice under the same name; fetch spare
# results so dropping repeats still leaves enough alternatives.
_SPARE_FACTOR = 3


@dataclass
class SlotResult:
    slot: Slot
    products: list[Product]


def _slot_filters(
    slot: Slot, user_filters: SearchFilter, llm_filters: SearchFilter, gender: str | None
) -> tuple[SearchFilter, SearchFilter]:
    """(vector filters, keyword filters) for one slot.

    Mirrors POST /search: the user's filters constrain both searches and the
    LLM's only the keyword one. The slot's own restriction replaces any
    category the user or LLM set, since an outfit spans categories.
    """
    slot_restriction = {
        "category": slot.category,
        "subcategories": list(slot.subcategories) if slot.subcategories else None,
    }
    vector = user_filters.model_copy(update={"gender": gender, **slot_restriction})
    keyword = merge_filters(vector, llm_filters).model_copy(update=slot_restriction)
    return vector, keyword


def _distinct_by_name(products: list[Product], limit: int) -> list[Product]:
    seen: set[str] = set()
    distinct = []
    for product in products:
        key = " ".join(product.name.lower().split())
        if key not in seen:
            seen.add(key)
            distinct.append(product)
    return distinct[:limit]


def _majority_gender(products: list[Product]) -> str | None:
    votes = Counter(p.gender for p in products if p.gender in _WEARER_GENDERS)
    return votes.most_common(1)[0][0] if votes else None


def build_outfit(
    session: Session,
    provider: EmbeddingProvider,
    vector_text: str,
    keyword_text: str,
    user_filters: SearchFilter,
    llm_filters: SearchFilter,
    per_slot: int,
) -> tuple[list[SlotResult], str | None, float]:
    """Returns (results per slot, the gender the outfit was built for, time in ms).

    The gender comes from the user's filter, else the LLM's, else a vote among
    the first slot's top results, so the outfit isn't a mix of men's and
    women's items.
    """
    start = time.perf_counter()

    def search(slot: Slot, gender: str | None, limit: int) -> list[Product]:
        vector_filters, keyword_filters = _slot_filters(slot, user_filters, llm_filters, gender)
        products, _, _ = search_hybrid(
            session,
            query_text=vector_text,
            provider=provider,
            filters=vector_filters,
            method=SearchMethod.HYBRID,
            limit=limit,
            keyword_query_text=keyword_text,
            keyword_filters=keyword_filters,
        )
        return products

    gender = user_filters.gender or llm_filters.gender
    first, *rest = OUTFIT_SLOTS
    if gender is None:
        gender = _majority_gender(search(first, None, _GENDER_VOTERS))

    results = [
        SlotResult(slot, _distinct_by_name(search(slot, gender, per_slot * _SPARE_FACTOR), per_slot))
        for slot in (first, *rest)
    ]
    return results, gender, (time.perf_counter() - start) * 1000
