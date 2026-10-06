"""Outfit builder API route."""
import logging

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.api.rate_limit import limit_search_rate
from app.api.routes.search import get_query_understanding_provider, get_search_provider
from app.db.database import get_session
from app.providers.base import EmbeddingProvider
from app.providers.llm_base import LLMProvider
from app.schemas.outfit import OutfitRequest, OutfitResponse, OutfitSlot
from app.schemas.search import QueryUnderstandingInfo, SearchFilter
from app.services.outfit import build_outfit
from app.services.query_understanding import get_catalogue_facets, search_texts, understand_query
from app.services.timing import server_timing_header, start_timing, timed
from core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/outfit", tags=["outfit"])


@router.post(
    "",
    response_model=OutfitResponse,
    # An outfit runs one search per slot, so it shares the search rate limit.
    dependencies=[Depends(limit_search_rate)],
    responses={429: {"description": "Too many searches; see the Retry-After header"}},
)
def outfit(
    request: OutfitRequest,
    response: Response,
    session: Session = Depends(get_session),
    provider: EmbeddingProvider = Depends(get_search_provider),
    llm_provider: LLMProvider = Depends(get_query_understanding_provider),
) -> OutfitResponse:
    """Build an outfit for an occasion: a top, bottom, footwear and accessory.

    Each slot is a hybrid search for the full query restricted to that slot's
    product group, so "beach this summer" decides which footwear ranks first.
    The LLM contributes gender, colour and season, exactly as in POST /search.
    """
    try:
        timings = start_timing()
        user_filters = request.filters or SearchFilter()
        if user_filters.availability is None:
            user_filters = user_filters.model_copy(update={"availability": True})

        understanding = None
        info = None
        llm_filters = SearchFilter()
        if settings.query_understanding_enabled:
            with timed("facets"):
                facets = get_catalogue_facets(session)
            with timed("llm"):
                understanding = understand_query(llm_provider, request.query, facets)
            llm_filters = understanding.filters
            info = QueryUnderstandingInfo(
                used_llm=understanding.used_llm,
                translated=understanding.translated,
                english_query=understanding.cleaned_query if understanding.translated else None,
                inferred_filters=understanding.filters.model_dump(
                    include={"category", "gender", "color", "season"}, exclude_none=True
                ),
                fallback_reason=understanding.fallback_reason,
            )

        vector_text, keyword_text = search_texts(request.query, understanding)
        results, gender, outfit_ms = build_outfit(
            session, provider, vector_text, keyword_text, user_filters, llm_filters, request.per_slot
        )
        timings["total"] = outfit_ms + timings.get("llm", 0.0) + timings.get("facets", 0.0)

        logger.info(
            "outfit_complete",
            extra={
                "query": request.query[:100],
                "gender": gender,
                "results": sum(len(r.products) for r in results),
                "outfit_ms": outfit_ms,
                "llm_used": bool(understanding and understanding.used_llm),
            },
        )
        response.headers["Server-Timing"] = server_timing_header(timings)

        return OutfitResponse(
            query=request.query,
            gender=gender,
            slots=[OutfitSlot(key=r.slot.key, label=r.slot.label, products=r.products) for r in results],
            took_ms=outfit_ms + timings.get("llm", 0.0),
            understanding=info,
        )
    except OperationalError as e:
        logger.error(f"Outfit failed, database unavailable: {e}")
        raise HTTPException(status_code=503, detail="Outfit builder is temporarily unavailable")
    except Exception:
        logger.exception("Outfit failed")
        raise HTTPException(status_code=500, detail="Outfit failed")
