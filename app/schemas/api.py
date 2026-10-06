"""API response schemas for HTTP endpoints."""

from decimal import Decimal

from pydantic import BaseModel


class ProductResponse(BaseModel):
    """Product data for catalogue listing API responses."""

    id: str
    external_product_id: str
    name: str
    category: str | None = None
    subcategory: str | None = None
    article_type: str | None = None
    gender: str | None = None
    color: str | None = None
    style: str | None = None
    season: str | None = None
    price: Decimal | None = None
    currency: str
    availability: bool

    class Config:
        from_attributes = True


class PaginatedProductResponse(BaseModel):
    """Paginated product list response."""

    items: list[ProductResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
