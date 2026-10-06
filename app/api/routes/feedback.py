"""Thumbs-up/down feedback on search results."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.rate_limit import limit_feedback_rate
from app.db.database import get_session
from app.db.models.product import Product
from app.schemas.feedback import FeedbackRequest, FeedbackResponse, FeedbackSummary, VotesResponse
from app.services.feedback import record_feedback, summarize_feedback, votes_for

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post(
    "",
    response_model=FeedbackResponse,
    dependencies=[Depends(limit_feedback_rate)],
    responses={404: {"description": "Unknown product"}, 429: {"description": "Too many feedback requests"}},
)
def submit_feedback(request: FeedbackRequest, session: Session = Depends(get_session)) -> FeedbackResponse:
    """Record a vote on one search result: 1 (relevant), -1 (not relevant) or 0 (remove my vote).

    Voting again on the same query and product replaces the previous vote.
    """
    if session.get(Product, request.product_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown product")
    return FeedbackResponse(vote=record_feedback(session, request))


@router.get("/votes", response_model=VotesResponse)
def my_votes(
    client_id: str = Query(..., min_length=8, max_length=64, pattern=r"^[A-Za-z0-9-]+$"),
    query: str = Query(..., min_length=1, max_length=500),
    session: Session = Depends(get_session),
) -> VotesResponse:
    """This client's votes for a query, so the UI can show them again."""
    return VotesResponse(votes=votes_for(session, client_id, query))


@router.get("/summary", response_model=FeedbackSummary)
def feedback_summary(
    limit: int = Query(10, ge=1, le=50, description="Rows in the per-query and recent lists"),
    session: Session = Depends(get_session),
) -> FeedbackSummary:
    """Totals, helpful rate, the queries with the most "not helpful" votes, and recent votes."""
    return summarize_feedback(session, limit=limit)
