from sqlalchemy import Column, String, Float, Boolean, DateTime, Text
from sqlalchemy.sql import func

from app.db.database import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(String, primary_key=True, index=True)
    external_product_id = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String, nullable=True)
    subcategory = Column(String, nullable=True)
    brand = Column(String, nullable=True)
    gender = Column(String, nullable=True)
    color = Column(String, nullable=True)
    material = Column(String, nullable=True)
    style = Column(String, nullable=True)
    season = Column(String, nullable=True)
    price = Column(Float, nullable=True)
    currency = Column(String, default="USD", nullable=False)
    availability = Column(Boolean, default=True, nullable=False)
    metadata = Column(Text, nullable=True)
    embedding = Column(String, nullable=True)  # pgvector stored as string (vector syntax)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )