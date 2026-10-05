"""Unit tests for the DB-backed catalogue facet vocabulary."""
from unittest.mock import patch

import pytest

from app.db.models.product import Product
from app.services.query_understanding import vocabulary
from app.services.query_understanding.vocabulary import get_catalogue_facets, load_catalogue_facets


def _product(pid: str, **kwargs) -> Product:
    return Product(
        id=pid,
        external_product_id=f"ext_{pid}",
        name=pid,
        search_text=pid,
        content_hash=f"hash_{pid}",
        **kwargs,
    )


@pytest.fixture
def catalogue(test_db):
    test_db.add_all([
        _product("p1", category="Apparel", gender="Men", color="Black", season="Summer"),
        _product("p2", category="Footwear", gender="Women", color="Blue", season="Winter"),
        _product("p3", category="Apparel", gender="Men", color="Black", season=None),
        _product("gone", category="Home", gender="Unisex", color="Lilac", season="Fall", availability=False),
    ])
    test_db.commit()
    return test_db


class TestLoadCatalogueFacets:
    def test_distinct_sorted_values_of_available_products(self, catalogue):
        facets = load_catalogue_facets(catalogue)

        assert facets == {
            "category": ["Apparel", "Footwear"],
            "gender": ["Men", "Women"],
            "color": ["Black", "Blue"],
            "season": ["Summer", "Winter"],
        }

    def test_new_catalogue_value_appears(self, catalogue):
        catalogue.add(_product("p4", category="Apparel", color="Lilac"))
        catalogue.commit()

        assert "Lilac" in load_catalogue_facets(catalogue)["color"]

    def test_empty_catalogue(self, test_db):
        assert load_catalogue_facets(test_db) == {"category": [], "gender": [], "color": [], "season": []}


class TestGetCatalogueFacetsCache:
    def test_cached_within_ttl(self, catalogue):
        first = get_catalogue_facets(catalogue)
        catalogue.add(_product("p4", color="Lilac"))
        catalogue.commit()

        assert get_catalogue_facets(catalogue) == first

    def test_refreshed_after_ttl(self, catalogue):
        get_catalogue_facets(catalogue)
        catalogue.add(_product("p4", color="Lilac"))
        catalogue.commit()

        with patch.object(vocabulary.settings, "catalogue_facets_cache_seconds", 0):
            assert "Lilac" in get_catalogue_facets(catalogue)["color"]

    def test_failed_refresh_keeps_previous_values(self, catalogue):
        first = get_catalogue_facets(catalogue)

        with patch.object(vocabulary.settings, "catalogue_facets_cache_seconds", 0), \
                patch.object(vocabulary, "load_catalogue_facets", side_effect=RuntimeError("db down")):
            assert get_catalogue_facets(catalogue) == first

    def test_failure_with_nothing_cached_raises(self, catalogue):
        with patch.object(vocabulary, "load_catalogue_facets", side_effect=RuntimeError("db down")):
            with pytest.raises(RuntimeError):
                get_catalogue_facets(catalogue)
