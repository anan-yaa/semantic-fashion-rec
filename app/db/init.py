from sqlalchemy import create_engine

from app.db.database import Base


def init_db(database_url: str) -> None:
    """Initialize database tables."""
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)