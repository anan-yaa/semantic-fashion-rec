from sqlalchemy import (
    Column,
    String,
    Numeric,
    Boolean,
    DateTime,
    Text,
    JSON,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID, TSVECTOR
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector

from app.db.database import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True)
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
    embedding = Column(Vector, nullable=True)
    search_text = Column(Text, nullable=True)  # For full-text search
    search_vector = Column(TSVECTOR, nullable=True)
    content_hash = Column(String, nullable=True, index=True)  # SHA256 of concatenated text
    embedded_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("idx_category_availability", "category", "availability"),
        Index("idx_brand_gender", "brand", "gender"),
    )