"""Re-order ranked search results by a user-chosen sort."""

from app.db.models.product import Product
from app.schemas.search import SortOrder


def _year(product: Product):
    year = (product.attributes or {}).get("year")
    # Stored as int or float ("2017.0") depending on the source record.
    return year if isinstance(year, (int, float)) and not isinstance(year, bool) else None


def sort_products(products: list[Product], sort: SortOrder) -> list[Product]:
    """Sort already-ranked results. Ties keep their relevance order (stable sort)."""
    if sort == SortOrder.NEWEST:
        # Products without a year go last.
        return sorted(products, key=lambda p: (_year(p) is None, -(_year(p) or 0)))
    if sort == SortOrder.NAME:
        return sorted(products, key=lambda p: p.name.casefold())
    return list(products)
