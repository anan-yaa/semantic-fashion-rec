import os
from typing import Generator

import pytest
from sqlalchemy import create_engine, Text, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.exc import OperationalError
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import TSVECTOR

from app.db.database import Base
from app.db.repositories.product_repository import ProductRepository
from app.services.query_understanding.vocabulary import _reset_catalogue_facets_cache
from app.services.search.product_types import _reset_article_type_cache
from core.config import settings


@pytest.fixture(autouse=True)
def reset_catalogue_caches():
    """Catalogue vocabularies are cached per process; each test DB has its own values."""
    _reset_catalogue_facets_cache()
    _reset_article_type_cache()
    yield
    _reset_catalogue_facets_cache()
    _reset_article_type_cache()


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
#
# Schema is created from ORM metadata (which has the correct
# pgvector.sqlalchemy.Vector/TSVECTOR types) plus the index statements from
# migration 0002_day2_search_columns, rather than by running the real
# migrations - this keeps these tests independent of whichever revision the
# real dev database happens to be at.
#
# SAFETY: this fixture (and the one in test_migration.py) drops and recreates
# tables around every test. It defaults to a database NAMED DIFFERENTLY from
# the real one (DATABASE_URL's database, typically "fashion_rec") - same
# host/port, just "_test" appended - specifically so a developer who forgets
# to set TEST_POSTGRES_URL cannot accidentally wipe real catalogue/embedding
# data. _assert_safe_test_database() additionally refuses to run, hard, if
# TEST_POSTGRES_URL ever ends up pointing at the exact same database as
# DATABASE_URL, however that happened. A real incident earlier in this
# project (the default used to just copy DATABASE_URL) is why this exists.
def _default_test_postgres_url() -> str:
    real_url = make_url(settings.database_url)
    test_url = real_url.set(database=f"{real_url.database}_test")
    # str(url)/repr(url) mask the password (e.g. "***") - they're meant for
    # safe logging, not for actual connection use. render_as_string with
    # hide_password=False is required to get back a usable DSN.
    return test_url.render_as_string(hide_password=False)


TEST_POSTGRES_URL = os.environ.get("TEST_POSTGRES_URL", _default_test_postgres_url())


def _assert_safe_test_database() -> None:
    """Hard-refuse to run destructive test fixtures against the real database.

    This is the actual safety net - it holds regardless of what
    TEST_POSTGRES_URL is set to (default, env override, typo, whatever).
    """
    test_db = make_url(TEST_POSTGRES_URL)
    real_db = make_url(settings.database_url)
    same_target = (
        (test_db.host or "localhost") == (real_db.host or "localhost")
        and (test_db.port or 5432) == (real_db.port or 5432)
        and test_db.database == real_db.database
    )
    if same_target:
        raise RuntimeError(
            "Refusing to run: TEST_POSTGRES_URL resolves to the same database as "
            f"DATABASE_URL ({real_db.database!r} on {real_db.host}:{real_db.port}). "
            "This fixture drops and recreates tables - pointing it at the real "
            "database would destroy real data. Set TEST_POSTGRES_URL to a "
            "separate database."
        )


def _ensure_test_database_exists() -> None:
    """Create the TEST_POSTGRES_URL database if it doesn't exist yet.

    Connects to the admin "postgres" database to do so, since Postgres
    cannot CREATE DATABASE while connected to the database being created.
    """
    test_db = make_url(TEST_POSTGRES_URL)
    admin_url = test_db.set(database="postgres")
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": test_db.database},
            ).first()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{test_db.database}"'))
    finally:
        admin_engine.dispose()


def _postgres_available() -> bool:
    try:
        engine = create_engine(TEST_POSTGRES_URL)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except OperationalError:
        try:
            _ensure_test_database_exists()
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
    _assert_safe_test_database()

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
