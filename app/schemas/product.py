
from pydantic import BaseModel


class ProductIngestSchema(BaseModel):
    """Schema for raw HuggingFace dataset records."""

    id: int
    gender: str | None = None
    masterCategory: str | None = None
    subCategory: str | None = None
    articleType: str | None = None
    baseColour: str | None = None
    season: str | None = None
    year: float | None = None
    usage: str | None = None
    productDisplayName: str | None = None

    class Config:
        # Allow extra fields (e.g., image column) but ignore them
        extra = "ignore"


class ProductCreateSchema(BaseModel):
    """Schema for normalized product data ready for database insertion."""

    id: str
    external_product_id: str
    name: str
    description: str | None = None
    category: str | None = None
    subcategory: str | None = None
    brand: str | None = None
    gender: str | None = None
    color: str | None = None
    material: str | None = None
    style: str | None = None
    season: str | None = None
    price: str | None = None
    currency: str | None = None
    availability: bool = True
    attributes: dict | None = None
    search_text: str | None = None
    content_hash: str | None = None
