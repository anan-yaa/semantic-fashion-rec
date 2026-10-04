import logging

from fastapi import FastAPI, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from core.config import settings
from core.logging import setup_logging
from app.db.database import engine
from app.api.routes.products import router as products_router
from app.api.routes.search import router as search_router

# Configure logging before anything else
setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
)

# Allow the local Next.js dev server to call this API from the browser.
# Without this, every request from frontend/ fails CORS preflight (curl/pytest
# never hit this, since browsers are the only thing that enforces CORS).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# Register routes
app.include_router(products_router)
app.include_router(search_router)


@app.on_event("startup")
async def startup_event():
    """Run on application startup."""
    logger.info("Application starting up")
    logger.info(f"Environment: debug={settings.debug}, host={settings.host}, port={settings.port}")

    # Warn if query understanding is enabled but no API key provided
    if settings.query_understanding_enabled and not settings.gemini_api_key:
        logger.warning(
            "⚠️  query_understanding_enabled=True but gemini_api_key is not set. "
            "Query understanding will be auto-disabled at runtime. "
            "Set GEMINI_API_KEY environment variable to enable."
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