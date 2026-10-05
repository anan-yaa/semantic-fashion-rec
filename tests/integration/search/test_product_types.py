"""Integration tests for product-type detection and its use in hybrid search (PostgreSQL)."""
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.db.models.product import Product
from app.providers.fake import FakeEmbeddingProvider
from app.schemas.search import SearchFilter
from app.services import catalogue_cache
from app.services.keyword_index import build_keyword_index
from app.services.search import search_hybrid
from app.services.search.product_types import detect_article_types


def make_product(pid: str, name: str, article_type: str, **kwargs) -> Product:
    product = Product(
        id=pid,
        external_product_id=f"ext_{pid}",
        name=name,
        search_text=name.lower(),
        content_hash=f"hash_{pid}",
        attributes={"articleType": article_type},
        **kwargs,
    )
    product.embedding = FakeEmbeddingProvider().embed_passages([name.lower()])[0]
    return product


@pytest.fixture
def catalogue(postgres_session: Session) -> Session:
    postgres_session.add_all([
        make_product("jacket", "Men Black Jacket", "Jackets", gender="Men", color="Black"),
        make_product("wallet", "Men Black Leather Wallet", "Wallets", gender="Men", color="Black"),
        make_product("tshirt", "Men White Tshirt", "Tshirts", gender="Men"),
        make_product("shirt", "Men Blue Shirt", "Shirts", gender="Men"),
        make_product("formal", "Men Black Formal Shoes", "Formal Shoes", gender="Men"),
        make_product("sweater", "Men Grey Sweater", "Sweaters", gender="Men"),
        make_product("old_belt", "Brown Belt", "Belts", availability=False),
    ])
    postgres_session.commit()
    build_keyword_index(postgres_session, limit=100)
    return postgres_session


class TestDetectArticleTypes:
    @pytest.mark.parametrize(
        "query, expected",
        [
            ("black leather jacket for men", ["Jackets"]),
            ("jackets", ["Jackets"]),
            ("t-shirt for men", ["Tshirts"]),
            ("formal shoes", ["Formal Shoes"]),
            ("shoes", []),
            ("warm layer to wear under a jacket", []),
            ("shoes to go with a black jacket", []),
            ("I need an outfit to go to the beach this summer", []),
            ("नीली शर्ट", []),
        ],
    )
    def test_detection(self, catalogue, query, expected):
        assert detect_article_types(catalogue, query) == expected

    def test_unavailable_types_are_ignored(self, catalogue):
        assert detect_article_types(catalogue, "brown belt") == []

    def test_new_type_picked_up_after_cache_expiry(self, catalogue):
        assert detect_article_types(catalogue, "silk kurta") == []
        catalogue.add(make_product("kurta", "Women Silk Kurta", "Kurtas", gender="Women"))
        catalogue.commit()

        with patch.object(catalogue_cache.settings, "catalogue_facets_cache_seconds", 0):
            assert detect_article_types(catalogue, "silk kurta") == ["Kurtas"]


class TestHybridSearchWithProductType:
    def test_named_type_restricts_results(self, catalogue):
        results, _, _ = search_hybrid(
            catalogue, "black leather jacket for men", FakeEmbeddingProvider(),
            filters=SearchFilter(availability=True), limit=10,
        )

        assert [p.id for p in results] == ["jacket"]

    def test_query_without_type_is_unrestricted(self, catalogue):
        results, _, _ = search_hybrid(
            catalogue, "warm layer to wear under a jacket", FakeEmbeddingProvider(),
            filters=SearchFilter(availability=True), limit=10,
        )

        assert len(results) > 1

    def test_falls_back_when_no_product_of_type_matches_filters(self, catalogue):
        catalogue.add(make_product("w_wallet", "Women Red Wallet", "Wallets", gender="Women"))
        catalogue.commit()

        results, _, _ = search_hybrid(
            catalogue, "jacket", FakeEmbeddingProvider(),
            filters=SearchFilter(availability=True, gender="Women"), limit=10,
        )

        assert [p.id for p in results] == ["w_wallet"]

    def test_vector_and_keyword_methods_are_unchanged(self, catalogue):
        from app.schemas.search import SearchMethod

        results, _, _ = search_hybrid(
            catalogue, "black leather jacket for men", FakeEmbeddingProvider(),
            filters=SearchFilter(availability=True), method=SearchMethod.VECTOR, limit=10,
        )

        assert "wallet" in [p.id for p in results]
