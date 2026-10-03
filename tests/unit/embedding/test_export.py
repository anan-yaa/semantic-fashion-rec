"""Tests for the embedding-export selection/shaping logic."""
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.db.models.product import Product
from app.services.embedding.export import select_products_for_export, to_export_rows


def make_product(pid, created_at, **overrides) -> Product:
    defaults = dict(
        id=pid,
        external_product_id=f"ext_{pid}",
        name=f"Product {pid}",
        search_text=f"search text {pid}",
        content_hash=f"hash_{pid}",
        created_at=created_at,
    )
    defaults.update(overrides)
    return Product(**defaults)


class TestSelectProductsForExport:
    def test_only_products_needing_embedding_are_selected(self, test_db: Session):
        t0 = datetime(2026, 1, 1)
        needs_embedding = make_product("p1", t0, embedding=None)
        already_embedded = make_product(
            "p2", t0, embedding=[0.1] * 768, embedding_content_hash="hash_p2"
        )
        test_db.add_all([needs_embedding, already_embedded])
        test_db.commit()

        selected = select_products_for_export(test_db)

        assert [p.id for p in selected] == ["p1"]

    def test_ordering_is_deterministic_across_repeated_calls(self, test_db: Session):
        t0 = datetime(2026, 1, 1)
        # Same created_at on purpose - exercises the (created_at, id) tie-break.
        products = [make_product(f"p{i}", t0) for i in [3, 1, 2]]
        test_db.add_all(products)
        test_db.commit()

        first = [p.id for p in select_products_for_export(test_db)]
        second = [p.id for p in select_products_for_export(test_db)]

        assert first == second == ["p1", "p2", "p3"]

    def test_created_at_is_primary_sort_key(self, test_db: Session):
        t0 = datetime(2026, 1, 1)
        t1 = t0 + timedelta(days=1)
        newer = make_product("z_newer", t1)
        older = make_product("a_older", t0)
        test_db.add_all([newer, older])
        test_db.commit()

        selected = [p.id for p in select_products_for_export(test_db)]

        assert selected == ["a_older", "z_newer"]


class TestToExportRows:
    def test_shapes_products_into_rows(self):
        t0 = datetime(2026, 1, 1)
        products = [make_product("p1", t0)]

        rows = to_export_rows(products)

        assert len(rows) == 1
        assert rows[0].id == "p1"
        assert rows[0].external_product_id == "ext_p1"
        assert rows[0].content_hash == "hash_p1"
        assert rows[0].search_text == "search text p1"

    def test_products_with_no_search_text_are_excluded(self):
        t0 = datetime(2026, 1, 1)
        products = [make_product("p1", t0, search_text=None)]

        rows = to_export_rows(products)

        assert rows == []
