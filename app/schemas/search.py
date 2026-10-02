"""Search request/response schemas."""
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field
from decimal import Decimal

from app.schemas.api import ProductResponse


class SearchMethod(str, Enum):
    """Search method enumeration."""
    HYBRID = "hybrid"
    VECTOR = "vector"
    KEYWORD = "keyword"


class SearchFilter(BaseModel):
    """Filters for search results."""
    category: Optional[str] = None
    gender: Optional[str] = None
    color: Optional[str] = None
    season: Optional[str] = None
    availability: Optional[bool] = None


class SearchRequest(BaseModel):
    """Search request."""
    query: str = Field(..., min_length=1, max_length=1000)
    filters: Optional[SearchFilter] = None
    limit: int = Field(default=50, ge=1, le=100)
    method: SearchMethod = SearchMethod.HYBRID


class SearchResponse(BaseModel):
    """Search response."""
    products: List[ProductResponse]
    query: str
    method: SearchMethod
    total_products: int
    took_ms: float
