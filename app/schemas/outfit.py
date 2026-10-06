"""Outfit request/response schemas."""
from pydantic import BaseModel, Field

from app.schemas.api import ProductResponse
from app.schemas.search import QueryUnderstandingInfo, SearchFilter


class OutfitRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500, description="What the outfit is for")
    filters: SearchFilter | None = Field(
        None, description="gender, color, season and availability apply; category is replaced by the slots"
    )
    per_slot: int = Field(default=4, ge=1, le=8, description="Products per slot: the first is the pick, the rest alternatives")


class OutfitSlot(BaseModel):
    key: str
    label: str
    products: list[ProductResponse]


class OutfitResponse(BaseModel):
    query: str
    gender: str | None = Field(None, description="Who the outfit was built for, when it could be determined")
    slots: list[OutfitSlot]
    took_ms: float
    understanding: QueryUnderstandingInfo | None = None
