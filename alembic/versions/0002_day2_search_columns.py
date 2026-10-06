"""Day 2: Add search indexing columns and vector index.

Revision ID: 0002_day2_search_columns
Revises: 743be6084b59
Create Date: 2026-10-02 00:00:00.000000

"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = '0002_day2_search_columns'
down_revision = '743be6084b59'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade: add embedding tracking columns and indexes."""
    # Add tracking columns for change detection
    op.add_column('products', sa.Column('embedding_content_hash', sa.String(), nullable=True))
    op.add_column('products', sa.Column('search_indexed_hash', sa.String(), nullable=True))

    # Ensure embedding column is Vector(768) type (in case it was created as generic Vector)
    # Note: all rows are currently NULL, so we can safely convert
    op.execute('ALTER TABLE products ALTER COLUMN embedding TYPE vector(768) USING NULL::vector(768)')

    # Create HNSW index for cosine distance (vector_cosine_ops pairs with <=> operator)
    op.execute(
        '''CREATE INDEX idx_embedding_hnsw ON products
           USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=200)
           WHERE embedding IS NOT NULL'''
    )

    # Create GIN index for TSVECTOR full-text search
    op.execute(
        'CREATE INDEX idx_search_vector_gin ON products USING gin (search_vector) WHERE search_vector IS NOT NULL'
    )


def downgrade() -> None:
    """Downgrade: remove indexes and tracking columns."""
    # Drop indexes
    op.execute('DROP INDEX IF EXISTS idx_embedding_hnsw')
    op.execute('DROP INDEX IF EXISTS idx_search_vector_gin')

    # Remove tracking columns
    op.drop_column('products', 'search_indexed_hash')
    op.drop_column('products', 'embedding_content_hash')
