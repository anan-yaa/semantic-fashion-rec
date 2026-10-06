"""Request/response schemas for search-result feedback."""
from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from app.schemas.search import QueryUnderstandingInfo, SearchFilter, SearchMethod, SortOrder


class FeedbackRequest(BaseModel):
    """A vote on one search result. vote 0 removes an earlier vote."""

    client_id: str = Field(..., min_length=8, max_length=64, pattern=r"^[A-Za-z0-9-]+$",
                           description="Anonymous per-browser id")
    query: str = Field(..., min_length=1, max_length=500)
    product_id: str = Field(..., min_length=1, max_length=36)
    vote: Literal[-1, 0, 1]
    position: int = Field(..., ge=1, le=10_000, description="1-based rank of the result across pages")
    method: Optional[SearchMethod] = None
    sort: Optional[SortOrder] = None
    filters: Optional[SearchFilter] = None
    understanding: Optional[QueryUnderstandingInfo] = None


class FeedbackResponse(BaseModel):
    vote: int = Field(description="The vote now stored: 1, -1, or 0 if none")


class VotesResponse(BaseModel):
    votes: Dict[str, int] = Field(description="product_id -> vote for this client and query")


class QueryFeedback(BaseModel):
    query: str
    helpful: int
    not_helpful: int


class RecentFeedback(BaseModel):
    query: str
    product_id: str
    product_name: str
    vote: int
    position: int
    llm_used: Optional[bool]
    updated_at: datetime


class FeedbackSummary(BaseModel):
    total_votes: int
    helpful: int
    not_helpful: int
    helpful_rate: Optional[float] = Field(description="helpful / total_votes; null when there are no votes")
    queries: int
    clients: int
    most_not_helpful: List[QueryFeedback]
    recent: List[RecentFeedback]
