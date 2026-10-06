import logging
import threading
import uuid

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.routes.feedback import router as feedback_router
from app.api.routes.outfit import router as outfit_router
from app.api.routes.products import router as products_router
from app.api.routes.search import router as search_router
from app.db.database import engine
from core.config import settings
from core.logging import request_id_var, setup_logging

# Configure logging before anything else
setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
)

# Browsers enforce CORS (curl/pytest never do); origins come from CORS_ORIGINS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID", "Server-Timing"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Tag every log line of a request with an id, and return it to the caller."""
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
    token = request_id_var.set(request_id)
    try:
        response = await call_next(request)
    finally:
        request_id_var.reset(token)
    response.headers["X-Request-ID"] = request_id
    return response

# Register routes
app.include_router(products_router)
app.include_router(search_router)
app.include_router(outfit_router)
app.include_router(feedback_router)


def _warm_up_embedding_model() -> None:
    from app.api.routes.search import get_search_provider

    try:
        get_search_provider().warm_up()
    except Exception as e:
        logger.warning(f"Embedding model warm-up failed; the first search will load it instead: {e}")


@app.on_event("startup")
async def startup_event():
    """Run on application startup."""
    logger.info("Application starting up")
    logger.info(f"Environment: debug={settings.debug}, host={settings.host}, port={settings.port}")

    # Loading models takes tens of seconds to minutes; do it in the background
    # so the app starts immediately and the first search doesn't pay for it.
    if settings.warm_up_models_on_startup:
        threading.Thread(target=_warm_up_embedding_model, daemon=True).start()

    if not settings.query_understanding_enabled:
        return

    if settings.llm_provider == "ollama":
        if settings.warm_up_models_on_startup:
            from app.providers.ollama_llm import OllamaProvider

            # Ollama keeps the model loaded server-side, so a throwaway client is enough.
            provider = OllamaProvider(model=settings.ollama_model, base_url=settings.ollama_base_url)
            threading.Thread(target=provider.warm_up, daemon=True).start()
    elif not settings.gemini_api_key:
        logger.warning(
            "query_understanding_enabled=True but GEMINI_API_KEY is not set; "
            "searches will fall back to the raw query."
        )


@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown."""
    logger.info("Application shutting down")


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {"message": "API is running"}


@app.get("/health")
async def health_check():
    """Health check endpoint that verifies database connectivity.

    Returns:
        200 with healthy status if DB is connected.
        503 Service Unavailable if DB is down.
    """
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": "healthy", "database": "connected"}
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "database": "disconnected", "error": str(e)}
        )