"""Product catalogue API routes."""

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.database import get_session
from app.db.repositories.product_repository import ProductRepository
from app.schemas.api import PaginatedProductResponse
from app.schemas.search import SearchFilter, SortOrder
from app.services.query_understanding import get_catalogue_facets

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=PaginatedProductResponse)
def list_products(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(24, ge=1, le=100, description="Items per page"),
    category: str | None = Query(None),
    gender: str | None = Query(None),
    color: str | None = Query(None),
    season: str | None = Query(None),
    sort: SortOrder = Query(SortOrder.RELEVANCE, description="relevance = catalogue order"),
    session: Session = Depends(get_session),
) -> PaginatedProductResponse:
    """
    List available products with optional filters, sorting and pagination.

    Products removed from the catalogue feed are kept as unavailable and are
    not listed, matching search.

    Returns:
    - items: List of products on this page
    - total: Total number of matching products
    - page: Current page number
    - page_size: Items per page
    - total_pages: Total number of pages
    """
    repo = ProductRepository(session)
    filters = SearchFilter(category=category, gender=gender, color=color, season=season)
    products, total = repo.list_available(
        filters, sort=sort, skip=(page - 1) * page_size, limit=page_size
    )

    return PaginatedProductResponse(
        items=products,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/facets", response_model=dict[str, list[str]])
def list_facets(session: Session = Depends(get_session)) -> dict[str, list[str]]:
    """Filter values present among available products: category, gender, color, season."""
    return get_catalogue_facets(session)
