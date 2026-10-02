from typing import Optional
from pydantic import BaseModel, Field


class ProductIngestSchema(BaseModel):
    """Schema for raw HuggingFace dataset records."""

    id: int
    gender: Optional[str] = None
    masterCategory: Optional[str] = None
    subCategory: Optional[str] = None
    articleType: Optional[str] = None
    baseColour: Optional[str] = None
    season: Optional[str] = None
    year: Optional[float] = None
    usage: Optional[str] = None
    productDisplayName: Optional[str] = None

    class Config:
        # Allow extra fields (e.g., image column) but ignore them
        extra = "ignore"


class ProductCreateSchema(BaseModel):
    """Schema for normalized product data ready for database insertion."""

    id: str
    external_product_id: str
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    brand: Optional[str] = None
    gender: Optional[str] = None
    color: Optional[str] = None
    material: Optional[str] = None
    style: Optional[str] = None
    season: Optional[str] = None
    price: Optional[str] = None
    currency: Optional[str] = None
    availability: bool = True
    attributes: Optional[dict] = None
    search_text: Optional[str] = None
    content_hash: Optional[str] = None
