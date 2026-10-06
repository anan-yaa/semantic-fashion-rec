"""Search request/response schemas."""
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.api import ProductResponse


class SearchMethod(str, Enum):
    """Search method enumeration."""
    HYBRID = "hybrid"
    VECTOR = "vector"
    KEYWORD = "keyword"


class SortOrder(str, Enum):
    """Result ordering. The catalogue has no prices or ratings, so these are the meaningful ones."""
    RELEVANCE = "relevance"
    NEWEST = "newest"  # By the dataset's product year
    NAME = "name"


# Search ranks this many top matches, then pages through them.
MAX_SEARCH_RESULTS = 100


class SearchFilter(BaseModel):
    """Filters for search results."""
    category: str | None = None
    gender: str | None = None
    color: str | None = None
    season: str | None = None
    availability: bool | None = None


class SearchRequest(BaseModel):
    """Search request."""
    # Cap query length to bound LLM token usage and prompt-injection surface.
    # Typical fashion queries are <100 chars; 500 is ample (≈125 tokens at 4 chars/token).
    query: str = Field(..., min_length=1, max_length=500, description="Search query (max 500 chars)")
    filters: SearchFilter | None = None
    limit: int = Field(default=50, ge=1, le=100, description="Results per page")
    page: int = Field(default=1, ge=1, description="1-indexed page of the top matches")
    sort: SortOrder = SortOrder.RELEVANCE
    method: SearchMethod = SearchMethod.HYBRID


class QueryUnderstandingInfo(BaseModel):
    """What the LLM understood from the query, for display."""
    used_llm: bool
    translated: bool = Field(False, description="The query wasn't English and was searched in English")
    english_query: str | None = Field(None, description="The English translation searched, when translated")
    inferred_filters: dict[str, str] = Field(
        default_factory=dict, description="Non-empty LLM-inferred filters, e.g. {'color': 'Red'}"
    )
    fallback_reason: Literal["unsupported_query", "llm_unavailable"] | None = None


class SearchResponse(BaseModel):
    """Search response."""
    products: list[ProductResponse]
    query: str
    method: SearchMethod
    total_products: int = Field(description=f"Number of matches across all pages (at most {MAX_SEARCH_RESULTS})")
    page: int = 1
    page_size: int
    total_pages: int
    took_ms: float
    understanding: QueryUnderstandingInfo | None = Field(
        None, description="Null when query understanding is disabled"
    )
