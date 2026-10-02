import os
from typing import Generator

import pytest
from sqlalchemy import create_engine, Text, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.exc import OperationalError
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


# PostgreSQL integration test fixture.
# NOTE: Phase 1 migration 743be6084b59 cannot run as-is (postgresql.Vector does
# not exist; see Day 2 report). Schema is created from ORM metadata (which has
# the correct pgvector.sqlalchemy.Vector/TSVECTOR types) plus the index
# statements from migration 0002_day2_search_columns, so these tests still
# exercise the real indexes without depending on the broken migration file.
TEST_POSTGRES_URL = os.environ.get(
    "TEST_POSTGRES_URL",
    "postgresql+psycopg://fashion_rec:dev_password@localhost:5432/fashion_rec",
)


def _postgres_available() -> bool:
    try:
        engine = create_engine(TEST_POSTGRES_URL)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except OperationalError:
        return False


@pytest.fixture(scope="function")
def postgres_session() -> Generator[Session, None, None]:
    """Create a fresh PostgreSQL test database for each test.

    Skips the test if no PostgreSQL instance is reachable at TEST_POSTGRES_URL.
    """
    if not _postgres_available():
        pytest.skip(f"PostgreSQL not available at {TEST_POSTGRES_URL}")

    engine = create_engine(TEST_POSTGRES_URL)

    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    # Apply the indexes migration 0002_day2_search_columns adds, since the
    # schema here is built from ORM metadata rather than via alembic.
    with engine.connect() as conn:
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_embedding_hnsw ON products "
            "USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=200) "
            "WHERE embedding IS NOT NULL"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_search_vector_gin ON products "
            "USING gin (search_vector) WHERE search_vector IS NOT NULL"
        ))
        conn.commit()

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()
