"""Integration tests for GET /products API endpoint."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.database import get_session
from app.services.ingestion import ingest_records


def ingest_test_products(session: Session, count: int = 50):
    """Helper: Ingest N test products into the database."""
    records = []
    for i in range(count):
        records.append(
            {
                "id": 10000 + i,
                "gender": "Men" if i % 2 == 0 else "Women",
                "masterCategory": "Apparel",
                "subCategory": "Topwear",
                "articleType": "Shirt",
                "baseColour": ["Red", "Blue", "Green", "Black"][i % 4],
                "season": ["Summer", "Winter", "Spring", "Fall"][i % 4],
                "year": 2023,
                "usage": "Casual",
                "productDisplayName": f"Test Product {i:04d}",
            }
        )
    ingest_records(session, records)


class TestProductsListEndpoint:
    """Test suite for GET /products endpoint."""

    @pytest.fixture(autouse=True)
    def setup_client(self, test_db):
        """Override database dependency for each test."""
        def override_get_session():
            yield test_db

        app.dependency_overrides[get_session] = override_get_session
        self.client = TestClient(app)
        yield
        # Cleanup
        app.dependency_overrides.clear()

    def test_list_products_success(self, test_db):
        """Test successful product listing with default pagination."""
        ingest_test_products(test_db, count=50)

        response = self.client.get("/products")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert "total_pages" in data
        assert data["total"] == 50
        assert data["page"] == 1
        assert data["page_size"] == 24
        assert len(data["items"]) == 24

    def test_list_products_default_page_size(self, test_db):
        """Test default page_size is 24."""
        ingest_test_products(test_db, count=30)

        response = self.client.get("/products")

        data = response.json()
        assert data["page_size"] == 24
        assert len(data["items"]) == 24

    def test_list_products_custom_page_size(self, test_db):
        """Test custom page_size parameter."""
        ingest_test_products(test_db, count=30)

        response = self.client.get("/products?page_size=10")

        data = response.json()
        assert data["page_size"] == 10
        assert len(data["items"]) == 10

    def test_list_products_second_page(self, test_db):
        """Test pagination to second page."""
        ingest_test_products(test_db, count=50)

        response = self.client.get("/products?page=2&page_size=20")

        data = response.json()
        assert data["page"] == 2
        assert data["page_size"] == 20
        assert len(data["items"]) == 20
        assert data["total"] == 50
        assert data["total_pages"] == 3

    def test_list_products_last_page(self, test_db):
        """Test last page with incomplete set."""
        ingest_test_products(test_db, count=25)

        # Page 1 has 24, page 2 has 1
        response = self.client.get("/products?page=2&page_size=24")

        data = response.json()
        assert data["page"] == 2
        assert len(data["items"]) == 1
        assert data["total"] == 25
        assert data["total_pages"] == 2

    def test_list_products_total_pages_calculation(self, test_db):
        """Test total_pages is calculated correctly."""
        ingest_test_products(test_db, count=100)

        response = self.client.get("/products?page_size=30")

        data = response.json()
        expected_total_pages = (100 + 30 - 1) // 30  # = 4
        assert data["total_pages"] == expected_total_pages

    def test_list_products_invalid_page_zero(self, test_db):
        """Test page=0 returns validation error."""
        ingest_test_products(test_db, count=10)

        response = self.client.get("/products?page=0")

        assert response.status_code == 422  # Validation error

    def test_list_products_invalid_page_negative(self, test_db):
        """Test negative page returns validation error."""
        ingest_test_products(test_db, count=10)

        response = self.client.get("/products?page=-1")

        assert response.status_code == 422

    def test_list_products_page_size_too_large(self, test_db):
        """Test page_size > 100 returns validation error."""
        ingest_test_products(test_db, count=10)

        response = self.client.get("/products?page_size=101")

        assert response.status_code == 422

    def test_list_products_page_size_zero(self, test_db):
        """Test page_size=0 returns validation error."""
        ingest_test_products(test_db, count=10)

        response = self.client.get("/products?page_size=0")

        assert response.status_code == 422

    def test_list_products_empty_database(self, test_db):
        """Test empty database returns empty items list."""
        response = self.client.get("/products")

        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["page"] == 1
        assert data["page_size"] == 24
        assert data["total_pages"] == 0

    def test_list_products_beyond_last_page(self, test_db):
        """Test requesting page beyond available pages returns empty."""
        ingest_test_products(test_db, count=10)

        response = self.client.get("/products?page=100&page_size=24")

        data = response.json()
        assert data["items"] == []
        assert data["total"] == 10
        assert data["page"] == 100

    def test_list_products_response_schema(self, test_db):
        """Test response schema matches expected structure."""
        ingest_test_products(test_db, count=5)

        response = self.client.get("/products?page=1&page_size=10")

        data = response.json()
        # Check top-level keys
        assert set(data.keys()) == {"items", "total", "page", "page_size", "total_pages"}
        # Check items is list
        assert isinstance(data["items"], list)
        # Check each item has required fields
        for item in data["items"]:
            assert "id" in item
            assert "external_product_id" in item
            assert "name" in item
            assert "category" in item
            assert "price" in item
            assert "currency" in item
            assert "availability" in item

    def test_list_products_field_types(self, test_db):
        """Test all product fields have correct types."""
        ingest_test_products(test_db, count=1)

        response = self.client.get("/products")

        data = response.json()
        item = data["items"][0]

        # Type checks
        assert isinstance(item["id"], str)
        assert isinstance(item["external_product_id"], str)
        assert isinstance(item["name"], str)
        assert isinstance(item["currency"], str)
        assert isinstance(item["availability"], bool)
        assert isinstance(data["total"], int)
        assert isinstance(data["page"], int)
        assert isinstance(data["page_size"], int)
        assert isinstance(data["total_pages"], int)

    def test_list_products_no_internal_fields(self, test_db):
        """Test internal fields are not exposed."""
        ingest_test_products(test_db, count=1)

        response = self.client.get("/products")

        data = response.json()
        item = data["items"][0]

        # These internal fields should NOT be in response
        assert "embedding" not in item
        assert "search_vector" not in item
        assert "search_text" not in item
        assert "content_hash" not in item
        assert "embedded_at" not in item
        assert "created_at" not in item
        assert "updated_at" not in item
        assert "attributes" not in item
        assert "description" not in item
        assert "brand" not in item
        assert "material" not in item

    def test_list_products_hides_unavailable(self, test_db):
        """Products dropped from the catalogue feed are not listed."""
        ingest_test_products(test_db, count=5)
        ingest_records(
            test_db,
            [{"id": 10000 + i, "productDisplayName": f"Test Product {i:04d}"} for i in range(3)],
            mark_missing_unavailable=True,
        )

        response = self.client.get("/products")

        data = response.json()
        assert data["total"] == 3
        assert all(item["availability"] for item in data["items"])

    def test_list_products_filters(self, test_db):
        ingest_test_products(test_db, count=8)

        data = self.client.get("/products?gender=Men&color=Red").json()

        assert data["total"] == 2
        assert all(p["gender"] == "Men" and p["color"] == "Red" for p in data["items"])

    def test_list_products_sort_by_name(self, test_db):
        ingest_test_products(test_db, count=5)

        names = [p["name"] for p in self.client.get("/products?sort=name").json()["items"]]

        assert names == sorted(names)

    def test_list_products_invalid_sort_rejected(self, test_db):
        assert self.client.get("/products?sort=price").status_code == 422

    def test_facets_lists_values_of_available_products(self, test_db):
        ingest_test_products(test_db, count=4)

        facets = self.client.get("/products/facets").json()

        assert facets["gender"] == ["Men", "Women"]
        assert facets["color"] == ["Black", "Blue", "Green", "Red"]
        assert set(facets) == {"category", "gender", "color", "season"}
