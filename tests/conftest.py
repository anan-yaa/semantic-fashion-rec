from typing import Generator

import pytest
from sqlalchemy import create_engine, Text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.compiler import compiles
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import TSVECTOR

from app.db.database import Base
from app.db.repositories.product_repository import ProductRepository


@compiles(Vector, "sqlite")
def compile_vector(element, compiler, **kw):
    """Render Vector as TEXT for SQLite tests."""
    return "TEXT"


@compiles(TSVECTOR, "sqlite")
def compile_tsvector(element, compiler, **kw):
    """Render TSVECTOR as TEXT for SQLite tests."""
    return "TEXT"


# Use SQLite for testing (in-memory)
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="function")
def test_db() -> Generator[Session, None, None]:
    """Create a fresh test database for each test."""
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(engine)
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()
        # Clean up tables
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def repository(test_db: Session) -> ProductRepository:
    """Create a ProductRepository with test database."""
    return ProductRepository(test_db)
