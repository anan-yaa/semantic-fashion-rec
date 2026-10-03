"""Integration test for migration 0002_day2_search_columns.

Migration 743be6084b59 previously referenced `postgresql.Vector`, which does
not exist in sqlalchemy.dialects.postgresql (the correct type is
pgvector.sqlalchemy.Vector); this has since been fixed in that migration file.

To test migration 0002 in isolation without depending on 743be6084b59 having
actually been run against this database first, this test builds the schema
743be6084b59 produces via raw SQL directly, stamps alembic at 743be6084b59,
then runs `alembic upgrade head` for real. This exercises the actual
migration 0002 file through the actual alembic machinery.
"""
import os
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from alembic.config import Config
from alembic import command

from tests.conftest import TEST_POSTGRES_URL, _postgres_available, _assert_safe_test_database


PHASE1_FIXED_SCHEMA_SQL = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE products (
    id UUID NOT NULL,
    external_product_id VARCHAR NOT NULL,
    name VARCHAR NOT NULL,
    description TEXT,
    category VARCHAR,
    subcategory VARCHAR,
    brand VARCHAR,
    gender VARCHAR,
    color VARCHAR,
    material VARCHAR,
    style VARCHAR,
    season VARCHAR,
    price NUMERIC(10,2),
    currency VARCHAR NOT NULL DEFAULT 'USD',
    availability BOOLEAN NOT NULL DEFAULT true,
    attributes JSON,
    embedding vector,
    search_text TEXT,
    search_vector TSVECTOR,
    content_hash VARCHAR,
    embedded_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (id),
    UNIQUE (external_product_id)
);

CREATE INDEX idx_category ON products (category);
CREATE INDEX idx_name ON products (name);
CREATE INDEX idx_brand ON products (brand);
CREATE INDEX idx_gender ON products (gender);
CREATE INDEX idx_availability ON products (availability);
CREATE INDEX idx_price ON products (price);
CREATE INDEX idx_content_hash ON products (content_hash);
CREATE UNIQUE INDEX idx_external_product_id ON products (external_product_id);
CREATE INDEX idx_category_availability ON products (category, availability);
CREATE INDEX idx_brand_gender ON products (brand, gender);
"""


@pytest.fixture
def fresh_postgres_for_migration():
    """A fresh PostgreSQL DB with alembic_version table cleared, for migration testing."""
    _assert_safe_test_database()

    if not _postgres_available():
        pytest.skip(f"PostgreSQL not available at {TEST_POSTGRES_URL}")

    engine = create_engine(TEST_POSTGRES_URL)
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS products CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE"))
        conn.commit()

    yield engine

    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS products CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE"))
        conn.commit()
    engine.dispose()


class TestMigration0002:
    """Test suite for migration 0002_day2_search_columns."""

    def test_migration_0002_applies_on_fixed_phase1_schema(self, fresh_postgres_for_migration):
        """Test that migration 0002 runs cleanly via the real alembic CLI machinery."""
        engine = fresh_postgres_for_migration

        # Build the Phase 1 schema (DDL-equivalent to 743be6084b59, with the
        # Vector type bug corrected) so 0002 has something to build on.
        with engine.connect() as conn:
            conn.execute(text(PHASE1_FIXED_SCHEMA_SQL))
            conn.commit()

        # Stamp alembic at 743be6084b59 (pretend Phase 1 already ran), then
        # run the real migration 0002 through alembic.
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        alembic_cfg = Config(os.path.join(repo_root, "alembic.ini"))
        alembic_cfg.set_main_option("sqlalchemy.url", TEST_POSTGRES_URL)

        command.stamp(alembic_cfg, "743be6084b59")
        command.upgrade(alembic_cfg, "head")

        # Verify migration 0002's effects
        with engine.connect() as conn:
            # New columns exist
            cols = conn.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='products' AND column_name IN "
                "('embedding_content_hash', 'search_indexed_hash')"
            )).fetchall()
            assert len(cols) == 2

            # embedding column is vector(768)
            dim_row = conn.execute(text(
                "SELECT atttypmod FROM pg_attribute "
                "WHERE attrelid = 'products'::regclass AND attname = 'embedding'"
            )).fetchone()
            assert dim_row is not None
            assert dim_row[0] == 768

            # HNSW index exists with vector_cosine_ops
            idx = conn.execute(text(
                "SELECT indexdef FROM pg_indexes "
                "WHERE tablename='products' AND indexname='idx_embedding_hnsw'"
            )).fetchone()
            assert idx is not None
            assert "hnsw" in idx[0].lower()
            assert "vector_cosine_ops" in idx[0]

            # GIN index on search_vector exists
            idx2 = conn.execute(text(
                "SELECT indexdef FROM pg_indexes "
                "WHERE tablename='products' AND indexname='idx_search_vector_gin'"
            )).fetchone()
            assert idx2 is not None
            assert "gin" in idx2[0].lower()

    def test_migration_0002_downgrade(self, fresh_postgres_for_migration):
        """Test that migration 0002 downgrade removes its columns and indexes."""
        engine = fresh_postgres_for_migration

        with engine.connect() as conn:
            conn.execute(text(PHASE1_FIXED_SCHEMA_SQL))
            conn.commit()

        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        alembic_cfg = Config(os.path.join(repo_root, "alembic.ini"))
        alembic_cfg.set_main_option("sqlalchemy.url", TEST_POSTGRES_URL)

        command.stamp(alembic_cfg, "743be6084b59")
        command.upgrade(alembic_cfg, "head")
        command.downgrade(alembic_cfg, "743be6084b59")

        with engine.connect() as conn:
            cols = conn.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='products' AND column_name IN "
                "('embedding_content_hash', 'search_indexed_hash')"
            )).fetchall()
            assert len(cols) == 0

            idx = conn.execute(text(
                "SELECT indexname FROM pg_indexes "
                "WHERE tablename='products' AND indexname='idx_embedding_hnsw'"
            )).fetchone()
            assert idx is None

    def test_vector_cosine_ops_operator_is_cosine_distance(self, fresh_postgres_for_migration):
        """Verify vector_cosine_ops operator family pairs with <=> (catalog-level, not data-dependent)."""
        engine = fresh_postgres_for_migration

        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()

        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT amop.amopopr::regoperator::text AS operator
                FROM pg_opfamily opf
                JOIN pg_amop amop ON amop.amopfamily = opf.oid
                JOIN pg_am am ON am.oid = opf.opfmethod
                WHERE opf.opfname = 'vector_cosine_ops' AND am.amname = 'hnsw'
            """)).fetchone()

        assert result is not None
        assert "<=>" in result[0]
