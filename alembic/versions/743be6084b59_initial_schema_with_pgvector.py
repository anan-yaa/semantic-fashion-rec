"""Initial schema with pgvector

Revision ID: 743be6084b59
Revises:
Create Date: 2026-10-02 05:47:56.776126

"""
from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '743be6084b59'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        'products',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('external_product_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(), nullable=True),
        sa.Column('subcategory', sa.String(), nullable=True),
        sa.Column('brand', sa.String(), nullable=True),
        sa.Column('gender', sa.String(), nullable=True),
        sa.Column('color', sa.String(), nullable=True),
        sa.Column('material', sa.String(), nullable=True),
        sa.Column('style', sa.String(), nullable=True),
        sa.Column('season', sa.String(), nullable=True),
        sa.Column('price', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('currency', sa.String(), nullable=False, server_default='USD'),
        sa.Column('availability', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('attributes', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('embedding', Vector(768), nullable=True),
        sa.Column('search_text', sa.Text(), nullable=True),
        sa.Column('search_vector', postgresql.TSVECTOR(), nullable=True),
        sa.Column('content_hash', sa.String(), nullable=True),
        sa.Column('embedded_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('external_product_id')
    )

    op.create_index('idx_category', 'products', ['category'])
    op.create_index('idx_name', 'products', ['name'])
    op.create_index('idx_brand', 'products', ['brand'])
    op.create_index('idx_gender', 'products', ['gender'])
    op.create_index('idx_availability', 'products', ['availability'])
    op.create_index('idx_price', 'products', ['price'])
    op.create_index('idx_content_hash', 'products', ['content_hash'])
    op.create_index('idx_external_product_id', 'products', ['external_product_id'], unique=True)
    op.create_index('idx_category_availability', 'products', ['category', 'availability'])
    op.create_index('idx_brand_gender', 'products', ['brand', 'gender'])


def downgrade() -> None:
    op.drop_index('idx_brand_gender', table_name='products')
    op.drop_index('idx_category_availability', table_name='products')
    op.drop_index('idx_external_product_id', table_name='products')
    op.drop_index('idx_content_hash', table_name='products')
    op.drop_index('idx_price', table_name='products')
    op.drop_index('idx_availability', table_name='products')
    op.drop_index('idx_gender', table_name='products')
    op.drop_index('idx_brand', table_name='products')
    op.drop_index('idx_name', table_name='products')
    op.drop_index('idx_category', table_name='products')
    op.drop_table('products')
    op.execute("DROP EXTENSION IF EXISTS vector")
