"""API response schemas for HTTP endpoints."""

from typing import List, Optional
from decimal import Decimal
from pydantic import BaseModel


class ProductResponse(BaseModel):
    """Product data for catalogue listing API responses."""

    id: str
    external_product_id: str
    name: str
    category: Optional[str] = None
    subcategory: Optional[str] = None
    gender: Optional[str] = None
    color: Optional[str] = None
    style: Optional[str] = None
    season: Optional[str] = None
    price: Optional[Decimal] = None
    currency: str
    availability: bool

    class Config:
        from_attributes = True


class PaginatedProductResponse(BaseModel):
    """Paginated product list response."""

    items: List[ProductResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
