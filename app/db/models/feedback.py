from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from app.db.database import Base


class SearchFeedback(Base):
    """A thumbs-up/down vote on one search result.

    One row per (client, normalized query, product): voting again replaces the
    previous vote. The search context (position, method, filters, what the LLM
    understood) is stored so feedback can later be analyzed or turned into
    evaluation labels.
    """

    __tablename__ = "search_feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    client_id = Column(String(64), nullable=False)  # anonymous per-browser id
    query = Column(String(500), nullable=False)
    query_normalized = Column(String(500), nullable=False, index=True)
    product_id = Column(String(36), ForeignKey("products.id"), nullable=False, index=True)
    vote = Column(SmallInteger, nullable=False)  # 1 = relevant, -1 = not relevant
    position = Column(Integer, nullable=False)  # 1-based rank across pages
    search_method = Column(String(16), nullable=True)
    sort = Column(String(16), nullable=True)
    filters = Column(JSON, nullable=True)
    llm_used = Column(Boolean, nullable=True)
    # English text the query was searched with, when the LLM translated it
    llm_keywords = Column(String(500), nullable=True)
    llm_filters = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("client_id", "query_normalized", "product_id", name="uq_feedback_client_query_product"),
        CheckConstraint("vote IN (-1, 1)", name="ck_feedback_vote"),
        CheckConstraint("position >= 1", name="ck_feedback_position"),
        Index("idx_feedback_updated_at", "updated_at"),
    )
