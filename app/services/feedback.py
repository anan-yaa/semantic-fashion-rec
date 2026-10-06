"""Store and summarize thumbs-up/down feedback on search results."""
from typing import Dict

from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models.feedback import SearchFeedback
from app.db.models.product import Product
from app.schemas.feedback import FeedbackRequest, FeedbackSummary, QueryFeedback, RecentFeedback


def normalize_query(query: str) -> str:
    """Votes on "Red Dress " and "red dress" belong to the same query."""
    return " ".join(query.lower().split())


def record_feedback(session: Session, request: FeedbackRequest) -> int:
    """Insert, update or (vote 0) remove this client's vote. Returns the vote now stored."""
    key = (request.client_id, normalize_query(request.query), request.product_id)
    existing = _find(session, *key)

    if request.vote == 0:
        if existing is not None:
            session.delete(existing)
            session.commit()
        return 0

    understanding = request.understanding
    values = dict(
        query=request.query,
        vote=request.vote,
        position=request.position,
        search_method=request.method.value if request.method else None,
        sort=request.sort.value if request.sort else None,
        filters=request.filters.model_dump(exclude_none=True) if request.filters else None,
        llm_used=understanding.used_llm if understanding else None,
        llm_keywords=understanding.english_query if understanding else None,
        llm_filters=understanding.inferred_filters if understanding else None,
    )
    if existing is None:
        session.add(SearchFeedback(client_id=key[0], query_normalized=key[1], product_id=key[2], **values))
        try:
            session.commit()
        except IntegrityError:
            # The same vote arrived twice at once (double click); update the row that won.
            session.rollback()
            existing = _find(session, *key)
    if existing is not None:
        for name, value in values.items():
            setattr(existing, name, value)
        session.commit()
    return request.vote


def _find(session: Session, client_id: str, query_normalized: str, product_id: str):
    return session.execute(
        select(SearchFeedback).where(
            SearchFeedback.client_id == client_id,
            SearchFeedback.query_normalized == query_normalized,
            SearchFeedback.product_id == product_id,
        )
    ).scalar_one_or_none()


def votes_for(session: Session, client_id: str, query: str) -> Dict[str, int]:
    rows = session.execute(
        select(SearchFeedback.product_id, SearchFeedback.vote).where(
            SearchFeedback.client_id == client_id,
            SearchFeedback.query_normalized == normalize_query(query),
        )
    )
    return {product_id: vote for product_id, vote in rows}


def summarize_feedback(session: Session, limit: int = 10) -> FeedbackSummary:
    helpful = func.sum(case((SearchFeedback.vote == 1, 1), else_=0))
    not_helpful = func.sum(case((SearchFeedback.vote == -1, 1), else_=0))

    total, up, down, queries, clients = session.execute(
        select(
            func.count(SearchFeedback.id),
            helpful,
            not_helpful,
            func.count(func.distinct(SearchFeedback.query_normalized)),
            func.count(func.distinct(SearchFeedback.client_id)),
        )
    ).one()
    up, down = up or 0, down or 0

    worst = session.execute(
        select(func.min(SearchFeedback.query), helpful.label("up"), not_helpful.label("down"))
        .group_by(SearchFeedback.query_normalized)
        .having(not_helpful > 0)
        .order_by(not_helpful.desc(), func.count(SearchFeedback.id).desc(), func.min(SearchFeedback.query))
        .limit(limit)
    ).all()

    recent = session.execute(
        select(SearchFeedback, Product.name)
        .join(Product, Product.id == SearchFeedback.product_id)
        .order_by(SearchFeedback.updated_at.desc(), SearchFeedback.id.desc())
        .limit(limit)
    ).all()

    return FeedbackSummary(
        total_votes=total,
        helpful=up,
        not_helpful=down,
        helpful_rate=(up / total) if total else None,
        queries=queries,
        clients=clients,
        most_not_helpful=[QueryFeedback(query=q, helpful=u, not_helpful=d) for q, u, d in worst],
        recent=[
            RecentFeedback(
                query=f.query,
                product_id=f.product_id,
                product_name=name,
                vote=f.vote,
                position=f.position,
                llm_used=f.llm_used,
                updated_at=f.updated_at,
            )
            for f, name in recent
        ],
    )
