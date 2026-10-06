"""POST /outfit: one slot per product group, a single gender across the outfit."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import app.api.routes.search as search_route
from app.db.database import get_session
from app.db.models.product import Product
from app.main import app
from app.providers.fake import FakeEmbeddingProvider
from app.providers.fake_llm import FakeLLMProvider
from app.providers.llm_base import QueryUnderstanding
from app.schemas.search import SearchFilter
from app.services.keyword_index import build_keyword_index

QUERY = "outfit for the beach this summer"

# (subcategory, category) of each slot's products
GROUPS = [("Topwear", "Apparel"), ("Bottomwear", "Apparel"), ("Shoes", "Footwear"), ("Watches", "Accessories")]


class TestOutfit:
    @pytest.fixture(autouse=True)
    def setup_client(self, postgres_session: Session):
        def override_get_session():
            yield postgres_session

        app.dependency_overrides[get_session] = override_get_session
        app.dependency_overrides[search_route.get_search_provider] = lambda: FakeEmbeddingProvider()
        app.dependency_overrides[search_route.get_query_understanding_provider] = lambda: FakeLLMProvider()
        self.client = TestClient(app)
        self.session = postgres_session
        yield
        app.dependency_overrides.clear()

    def _seed(self, men_per_group: int = 3, women_per_group: int = 1):
        provider = FakeEmbeddingProvider()
        for subcategory, category in GROUPS:
            for gender, count in (("Men", men_per_group), ("Women", women_per_group)):
                for i in range(count):
                    pid = f"{subcategory}_{gender}_{i}"
                    text = f"summer beach {subcategory.lower()} {gender.lower()}"
                    product = Product(
                        id=pid,
                        external_product_id=f"ext_{pid}",
                        name=f"{text} {i}",
                        search_text=text,
                        content_hash=f"hash_{pid}",
                        category=category,
                        subcategory=subcategory,
                        gender=gender,
                        season="Summer",
                    )
                    product.embedding = provider.embed_passages([text])[0]
                    self.session.add(product)
        self.session.commit()
        build_keyword_index(self.session, limit=1000)

    def _outfit(self, **body):
        response = self.client.post("/outfit", json={"query": QUERY, **body})
        assert response.status_code == 200, response.text
        return response.json()

    def test_each_slot_holds_only_its_own_product_group(self):
        self._seed()
        data = self._outfit()

        assert [s["key"] for s in data["slots"]] == ["top", "bottom", "footwear", "accessory"]
        expected = {"top": "Topwear", "bottom": "Bottomwear", "footwear": "Shoes", "accessory": "Watches"}
        for slot in data["slots"]:
            assert slot["products"], slot["key"]
            assert {p["subcategory"] for p in slot["products"]} == {expected[slot["key"]]}

    def test_gender_is_taken_from_the_majority_when_nothing_states_it(self):
        self._seed(men_per_group=3, women_per_group=1)
        data = self._outfit()

        assert data["gender"] == "Men"
        assert {p["gender"] for s in data["slots"] for p in s["products"]} == {"Men"}

    def test_user_gender_filter_wins_over_the_majority(self):
        self._seed(men_per_group=3, women_per_group=1)
        data = self._outfit(filters={"gender": "Women"})

        assert data["gender"] == "Women"
        assert {p["gender"] for s in data["slots"] for p in s["products"]} == {"Women"}

    def test_llm_inferred_gender_is_used(self):
        self._seed(men_per_group=3, women_per_group=1)
        canned = QueryUnderstanding(cleaned_query=QUERY, filters=SearchFilter(gender="Women"))
        app.dependency_overrides[search_route.get_query_understanding_provider] = (
            lambda: FakeLLMProvider(canned_responses={QUERY: canned})
        )
        data = self._outfit()

        assert data["gender"] == "Women"
        assert data["understanding"]["inferred_filters"] == {"gender": "Women"}

    def test_per_slot_limits_products_per_slot(self):
        self._seed(men_per_group=5, women_per_group=0)
        data = self._outfit(per_slot=2)

        assert all(len(s["products"]) == 2 for s in data["slots"])

    def test_user_category_filter_does_not_empty_the_outfit(self):
        self._seed()
        data = self._outfit(filters={"category": "Footwear"})

        assert all(s["products"] for s in data["slots"])

    def test_slots_missing_from_the_catalogue_come_back_empty(self):
        self._seed()
        self.session.query(Product).filter(Product.subcategory == "Watches").delete()
        self.session.commit()
        data = self._outfit()

        by_key = {s["key"]: s["products"] for s in data["slots"]}
        assert by_key["accessory"] == []
        assert by_key["top"]

    def test_listings_with_the_same_name_appear_once_per_slot(self):
        self._seed(men_per_group=0, women_per_group=0)
        provider = FakeEmbeddingProvider()
        for i, name in enumerate(["Blue Jeans", "blue  jeans", "Grey Jeans"]):
            product = Product(
                id=f"dup{i}", external_product_id=f"ext_dup{i}", name=name, search_text=f"{name} beach",
                content_hash=f"h{i}", category="Apparel", subcategory="Bottomwear", gender="Men",
            )
            product.embedding = provider.embed_passages([f"{name} beach"])[0]
            self.session.add(product)
        self.session.commit()
        build_keyword_index(self.session, limit=100)

        bottoms = {s["key"]: s["products"] for s in self._outfit()["slots"]}["bottom"]

        assert sorted(p["name"].lower().replace("  ", " ") for p in bottoms) == ["blue jeans", "grey jeans"]

    def test_search_accepts_a_subcategories_filter(self):
        self._seed()
        response = self.client.post(
            "/search",
            json={"query": "summer beach", "method": "keyword", "filters": {"subcategories": ["Topwear"]}, "limit": 50},
        )

        assert response.status_code == 200
        products = response.json()["products"]
        assert products and {p["subcategory"] for p in products} == {"Topwear"}

    def test_outfit_is_rate_limited_like_search(self, monkeypatch):
        from app.api.rate_limit import search_rate_limiter

        self._seed()
        monkeypatch.setattr(search_route.settings, "rate_limit_enabled", True)
        monkeypatch.setattr("app.api.rate_limit.settings.rate_limit_enabled", True)
        search_rate_limiter.reset()
        statuses = [self.client.post("/outfit", json={"query": QUERY}).status_code for _ in range(15)]

        assert 429 in statuses
