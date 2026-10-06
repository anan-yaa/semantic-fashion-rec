"""Add search_feedback table for thumbs-up/down votes on search results.

Revision ID: 0003_search_feedback
Revises: 0002_day2_search_columns
Create Date: 2026-10-06 00:00:00.000000

"""
import sqlalchemy as sa

from alembic import op

revision = "0003_search_feedback"
down_revision = "0002_day2_search_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "search_feedback",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("client_id", sa.String(64), nullable=False),
        sa.Column("query", sa.String(500), nullable=False),
        sa.Column("query_normalized", sa.String(500), nullable=False),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("vote", sa.SmallInteger(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("search_method", sa.String(16), nullable=True),
        sa.Column("sort", sa.String(16), nullable=True),
        sa.Column("filters", sa.JSON(), nullable=True),
        sa.Column("llm_used", sa.Boolean(), nullable=True),
        sa.Column("llm_keywords", sa.String(500), nullable=True),
        sa.Column("llm_filters", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("client_id", "query_normalized", "product_id", name="uq_feedback_client_query_product"),
        sa.CheckConstraint("vote IN (-1, 1)", name="ck_feedback_vote"),
        sa.CheckConstraint("position >= 1", name="ck_feedback_position"),
    )
    op.create_index("ix_search_feedback_query_normalized", "search_feedback", ["query_normalized"])
    op.create_index("ix_search_feedback_product_id", "search_feedback", ["product_id"])
    op.create_index("idx_feedback_updated_at", "search_feedback", ["updated_at"])


def downgrade() -> None:
    op.drop_index("idx_feedback_updated_at", table_name="search_feedback")
    op.drop_index("ix_search_feedback_product_id", table_name="search_feedback")
    op.drop_index("ix_search_feedback_query_normalized", table_name="search_feedback")
    op.drop_table("search_feedback")
