from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Index,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.sql import func

from app.db.database import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(String(36), primary_key=True, index=True)
    external_product_id = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    category = Column(String, nullable=True, index=True)
    subcategory = Column(String, nullable=True)
    brand = Column(String, nullable=True, index=True)
    gender = Column(String, nullable=True, index=True)
    color = Column(String, nullable=True)
    material = Column(String, nullable=True)
    style = Column(String, nullable=True)
    season = Column(String, nullable=True)
    price = Column(Numeric(10, 2), nullable=True, index=True)
    currency = Column(String, default="USD", nullable=False)
    availability = Column(Boolean, default=True, nullable=False, index=True)
    attributes = Column(JSON, nullable=True)  # Renamed from metadata
    embedding = Column(Vector(768), nullable=True)
    search_text = Column(Text, nullable=True)  # For full-text search
    search_vector = Column(TSVECTOR, nullable=True)
    content_hash = Column(String, nullable=True, index=True)  # SHA256 of concatenated text
    embedding_content_hash = Column(String, nullable=True)  # Hash at time of embedding
    search_indexed_hash = Column(String, nullable=True)  # Hash at time of keyword indexing
    embedded_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    @property
    def article_type(self):
        """Product type from the dataset, e.g. "Jackets" (stored in attributes)."""
        return (self.attributes or {}).get("articleType")

    __table_args__ = (
        Index("idx_category_availability", "category", "availability"),
        Index("idx_brand_gender", "brand", "gender"),
    )