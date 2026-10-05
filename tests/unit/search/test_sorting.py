"""Unit tests for sorting ranked search results."""
from app.db.models.product import Product
from app.schemas.search import SortOrder
from app.services.search.sorting import sort_products


def _p(pid, name, year):
    return Product(id=pid, external_product_id=pid, name=name, attributes={"year": year} if year is not None else None)


RANKED = [_p("a", "zebra top", 2012), _p("b", "Alpha shirt", 2017.0), _p("c", "mango dress", None), _p("d", "beta tee", 2017)]


def test_relevance_keeps_ranking():
    assert [p.id for p in sort_products(RANKED, SortOrder.RELEVANCE)] == ["a", "b", "c", "d"]


def test_newest_first_with_ties_in_relevance_order_and_missing_years_last():
    assert [p.id for p in sort_products(RANKED, SortOrder.NEWEST)] == ["b", "d", "a", "c"]


def test_name_is_case_insensitive():
    assert [p.id for p in sort_products(RANKED, SortOrder.NAME)] == ["b", "d", "c", "a"]
