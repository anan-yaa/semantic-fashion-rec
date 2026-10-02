"""Product catalogue API routes."""

import logging
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.database import get_session
from app.db.repositories.product_repository import ProductRepository
from app.schemas.api import PaginatedProductResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=PaginatedProductResponse)
async def list_products(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(24, ge=1, le=100, description="Items per page"),
    session: Session = Depends(get_session),
) -> PaginatedProductResponse:
    """
    List all products with pagination.

    Query Parameters:
    - page: Page number (1-indexed, minimum 1)
    - page_size: Items per page (1-100, default 24)

    Returns:
    - items: List of products on this page
    - total: Total number of products in catalogue
    - page: Current page number
    - page_size: Items per page
    - total_pages: Total number of pages
    """
    repo = ProductRepository(session)

    # Calculate skip offset
    skip = (page - 1) * page_size

    # Fetch products and total count from repository
    products, total = repo.list_all(skip=skip, limit=page_size)

    # Calculate total pages
    total_pages = (total + page_size - 1) // page_size

    # Return paginated response with explicit schema
    return PaginatedProductResponse(
        items=products,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
