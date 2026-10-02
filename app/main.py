import logging

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
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

# Register routes
app.include_router(products_router)
app.include_router(search_router)


@app.on_event("startup")
async def startup_event():
    """Run on application startup."""
    logger.info("Application starting up")
    logger.info(f"Environment: debug={settings.debug}, host={settings.host}, port={settings.port}")


@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown."""
    logger.info("Application shutting down")


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {"message": "API is running"}


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint that verifies database connectivity."""
    try:
        with engine.connect() as connection:
            connection.execute("SELECT 1")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"status": "unhealthy", "database": "disconnected", "error": str(e)}