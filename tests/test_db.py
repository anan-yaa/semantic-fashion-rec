import uuid
from decimal import Decimal

import pytest

from app.db.models.product import Product
from app.db.repositories.product_repository import ProductRepository


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
class TestProductRepository:
    """Test suite for ProductRepository."""

    def test_create_product(self, repository: ProductRepository) -> None:
        """Test creating a product."""
        product = Product(
            id=str(uuid.uuid4()),
            external_product_id="ext-001",
            name="Test Jacket",
            description="A test jacket",
            category="jackets",
            subcategory="outerwear",
            brand="TestBrand",
            gender="male",
            color="blue",
            material="cotton",
            style="casual",
            season="spring",
            price=Decimal("99.99"),
            currency="USD",
            availability=True,
        )

        created = repository.create(product)
        assert created.id == product.id
        assert created.name == "Test Jacket"
        assert created.external_product_id == "ext-001"

    def test_get_by_id(self, repository: ProductRepository) -> None:
        """Test retrieving a product by ID."""
        product_id = str(uuid.uuid4())
        product = Product(
            id=product_id,
            external_product_id="ext-002",
            name="Test Shirt",
            category="shirts",
            price=Decimal("49.99"),
            currency="USD",
            availability=True,
        )
        repository.create(product)

        retrieved = repository.get_by_id(product_id)
        assert retrieved is not None
        assert retrieved.name == "Test Shirt"

    def test_get_by_external_id(self, repository: ProductRepository) -> None:
        """Test retrieving a product by external ID."""
        product = Product(
            id=str(uuid.uuid4()),
            external_product_id="ext-unique-123",
            name="Test Pants",
            category="pants",
            price=Decimal("79.99"),
            currency="USD",
            availability=True,
        )
        repository.create(product)

        retrieved = repository.get_by_external_id("ext-unique-123")
        assert retrieved is not None
        assert retrieved.name == "Test Pants"

    def test_list_active_with_pagination(self, repository: ProductRepository) -> None:
        """Test listing active products with pagination."""
        for i in range(5):
            product = Product(
                id=str(uuid.uuid4()),
                external_product_id=f"ext-{i}",
                name=f"Product {i}",
                category="test",
                price=Decimal("10.00"),
                currency="USD",
                availability=i % 2 == 0,
            )
            repository.create(product)

        products, total = repository.list_active(skip=0, limit=10)
        assert len(products) == 3  # 5 products, 3 available (i=0,2,4)
        assert total == 3

    def test_search_by_name(self, repository: ProductRepository) -> None:
        """Test searching products by name."""
        product = Product(
            id=str(uuid.uuid4()),
            external_product_id="ext-search-test",
            name="Blue Denim Jacket",
            category="jackets",
            price=Decimal("89.99"),
            currency="USD",
            availability=True,
        )
        repository.create(product)

        results = repository.search_by_name("Denim")
        assert len(results) >= 1
        assert results[0].name == "Blue Denim Jacket"

    def test_upsert_many(self, repository: ProductRepository) -> None:
        """Test upserting multiple products."""
        products = [
            Product(
                id=str(uuid.uuid4()),
                external_product_id=f"ext-bulk-{i}",
                name=f"Bulk Product {i}",
                category="bulk",
                price=Decimal("25.00"),
                currency="USD",
                availability=True,
            )
            for i in range(3)
        ]

        count = repository.upsert_many(products)
        assert count == 3

        all_products, total = repository.list_all(skip=0, limit=100)
        assert total >= 3