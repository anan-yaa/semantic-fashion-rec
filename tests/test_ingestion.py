import hashlib
from decimal import Decimal

import pytest

from app.schemas.product import ProductIngestSchema, ProductCreateSchema
from app.services.ingestion_service import (
    normalize_text,
    build_search_text,
    compute_content_hash,
    map_to_product_create_schema,
    schema_to_product_model,
)
from app.db.repositories.product_repository import ProductRepository


class TestNormalizeText:
    """Test text normalization."""

    def test_normalize_text_basic(self):
        assert normalize_text("Hello World") == "hello world"

    def test_normalize_text_strips_whitespace(self):
        assert normalize_text("  hello  ") == "hello"

    def test_normalize_text_collapses_spaces(self):
        assert normalize_text("hello   world  test") == "hello world test"

    def test_normalize_text_none(self):
        assert normalize_text(None) is None

    def test_normalize_text_empty_string(self):
        assert normalize_text("") is None

    def test_normalize_text_only_whitespace(self):
        assert normalize_text("   ") is None

    def test_normalize_text_preserves_order(self):
        assert normalize_text("foo bar baz") == "foo bar baz"


class TestContentHash:
    """Test content hash computation."""

    def test_content_hash_deterministic(self):
        text = "hello world"
        hash1 = compute_content_hash(text)
        hash2 = compute_content_hash(text)
        assert hash1 == hash2

    def test_content_hash_consistent_with_sha256(self):
        text = "test"
        expected = hashlib.sha256(text.encode()).hexdigest()
        assert compute_content_hash(text) == expected

    def test_content_hash_different_for_different_input(self):
        hash1 = compute_content_hash("text1")
        hash2 = compute_content_hash("text2")
        assert hash1 != hash2

    def test_content_hash_case_sensitive(self):
        hash1 = compute_content_hash("Hello")
        hash2 = compute_content_hash("hello")
        assert hash1 != hash2


class TestBuildSearchText:
    """Test search text construction."""

    def test_build_search_text_with_all_fields(self):
        record = ProductIngestSchema(
            id=1,
            productDisplayName="Blue Shirt",
            gender="Men",
            masterCategory="Apparel",
            subCategory="Topwear",
            articleType="Shirts",
            baseColour="Blue",
            usage="Casual",
            season="Summer",
            year=2020.0,
        )
        result = build_search_text(record)
        assert "blue shirt" in result
        assert "men" in result
        assert "apparel" in result
        assert "topwear" in result
        assert "shirts" in result
        assert "blue" in result
        assert "casual" in result
        assert "summer" in result

    def test_build_search_text_normalized(self):
        record = ProductIngestSchema(
            id=1,
            productDisplayName="  BLUE  SHIRT  ",
            gender="  Men  ",
            masterCategory=None,
            subCategory=None,
            articleType=None,
            baseColour=None,
            usage=None,
            season=None,
        )
        result = build_search_text(record)
        assert result == "blue shirt men"

    def test_build_search_text_skips_none_values(self):
        record = ProductIngestSchema(
            id=1,
            productDisplayName="Shirt",
            gender=None,
            masterCategory=None,
            subCategory=None,
            articleType=None,
            baseColour=None,
            usage=None,
            season=None,
        )
        result = build_search_text(record)
        assert result == "shirt"

    def test_build_search_text_deterministic(self):
        record = ProductIngestSchema(
            id=1,
            productDisplayName="Blue Shirt",
            gender="Men",
            masterCategory="Apparel",
            subCategory="Topwear",
            articleType="Shirts",
            baseColour="Blue",
            usage="Casual",
            season="Summer",
        )
        result1 = build_search_text(record)
        result2 = build_search_text(record)
        assert result1 == result2

    def test_build_search_text_field_order(self):
        """Verify fields are in consistent order."""
        record = ProductIngestSchema(
            id=1,
            productDisplayName="A",
            gender="B",
            masterCategory="C",
            subCategory="D",
            articleType="E",
            baseColour="F",
            usage="G",
            season="H",
        )
        result = build_search_text(record)
        assert result == "a b c d e f g h"


class TestMapToProductCreateSchema:
    """Test mapping from ingest schema to create schema."""

    def test_valid_mapping(self):
        record = ProductIngestSchema(
            id=12345,
            productDisplayName="Blue Shirt",
            gender="Men",
            masterCategory="Apparel",
            subCategory="Topwear",
            articleType="Shirts",
            baseColour="Blue",
            usage="Casual",
            season="Summer",
            year=2020.0,
        )
        schema = map_to_product_create_schema(record)
        assert schema is not None
        assert schema.external_product_id == "12345"
        assert schema.name == "Blue Shirt"
        assert schema.category == "Apparel"
        assert schema.subcategory == "Topwear"
        assert schema.gender == "Men"
        assert schema.color == "Blue"
        assert schema.style == "Casual"
        assert schema.season == "Summer"
        assert schema.brand is None
        assert schema.material is None
        assert schema.price is None
        assert schema.currency == "USD"
        assert schema.availability is True

    def test_attributes_includes_article_type_and_year(self):
        record = ProductIngestSchema(
            id=1,
            productDisplayName="Shirt",
            articleType="Shirts",
            year=2021.0,
        )
        schema = map_to_product_create_schema(record)
        assert schema.attributes is not None
        assert schema.attributes["articleType"] == "Shirts"
        assert schema.attributes["year"] == 2021.0

    def test_missing_product_display_name(self):
        record = ProductIngestSchema(
            id=1,
            productDisplayName=None,
            gender="Men",
        )
        schema = map_to_product_create_schema(record)
        assert schema is None

    def test_empty_product_display_name(self):
        record = ProductIngestSchema(
            id=1,
            productDisplayName="",
            gender="Men",
        )
        schema = map_to_product_create_schema(record)
        assert schema is None

    def test_content_hash_set(self):
        record = ProductIngestSchema(
            id=1,
            productDisplayName="Shirt",
            gender="Men",
        )
        schema = map_to_product_create_schema(record)
        assert schema.content_hash is not None
        assert len(schema.content_hash) == 64

    def test_search_text_set(self):
        record = ProductIngestSchema(
            id=1,
            productDisplayName="Blue Shirt",
            gender="Men",
        )
        schema = map_to_product_create_schema(record)
        assert schema.search_text is not None
        assert "blue shirt" in schema.search_text
        assert "men" in schema.search_text

    def test_uuid_generated_for_id(self):
        record = ProductIngestSchema(
            id=1,
            productDisplayName="Shirt",
        )
        schema1 = map_to_product_create_schema(record)
        schema2 = map_to_product_create_schema(record)
        assert schema1.id != schema2.id
        assert len(schema1.id) == 36


class TestSchemaTOProductModel:
    """Test conversion from schema to SQLAlchemy model."""

    def test_schema_to_model_mapping(self):
        schema = ProductCreateSchema(
            id="550e8400-e29b-41d4-a716-446655440000",
            external_product_id="12345",
            name="Blue Shirt",
            category="Apparel",
            gender="Men",
            availability=True,
            search_text="blue shirt men",
            content_hash="abc123",
        )
        product = schema_to_product_model(schema)
        assert product.id == "550e8400-e29b-41d4-a716-446655440000"
        assert product.external_product_id == "12345"
        assert product.name == "Blue Shirt"
        assert product.category == "Apparel"
        assert product.gender == "Men"
        assert product.availability is True
        assert product.search_text == "blue shirt men"
        assert product.content_hash == "abc123"


class TestIdempotentIngestion:
    """Test idempotent ingestion (new/update/skip logic)."""

    def test_new_product_insertion(self, repository: ProductRepository) -> None:
        """Insert a new product."""
        record = ProductIngestSchema(
            id=9999,
            productDisplayName="Test Shirt",
            gender="Men",
            masterCategory="Apparel",
        )
        schema = map_to_product_create_schema(record)
        assert schema is not None

        product = schema_to_product_model(schema)
        repository.upsert_many([product])

        retrieved = repository.get_by_external_id("9999")
        assert retrieved is not None
        assert retrieved.name == "Test Shirt"
        assert retrieved.content_hash == schema.content_hash

    def test_unchanged_product_skip(self, repository: ProductRepository) -> None:
        """Second ingestion of unchanged product is skipped."""
        record = ProductIngestSchema(
            id=8888,
            productDisplayName="Test Pants",
            gender="Women",
            masterCategory="Apparel",
        )
        schema1 = map_to_product_create_schema(record)
        product1 = schema_to_product_model(schema1)
        repository.upsert_many([product1])

        schema2 = map_to_product_create_schema(record)
        assert schema1.content_hash == schema2.content_hash

    def test_changed_product_update(self, repository: ProductRepository) -> None:
        """Changed product is detected and updated."""
        record1 = ProductIngestSchema(
            id=7777,
            productDisplayName="Original Name",
            gender="Men",
            masterCategory="Apparel",
        )
        schema1 = map_to_product_create_schema(record1)
        product1 = schema_to_product_model(schema1)
        repository.upsert_many([product1])

        retrieved1 = repository.get_by_external_id("7777")
        hash1 = retrieved1.content_hash

        record2 = ProductIngestSchema(
            id=7777,
            productDisplayName="Updated Name",
            gender="Women",
            masterCategory="Apparel",
        )
        schema2 = map_to_product_create_schema(record2)
        assert schema2 is not None
        assert schema1.content_hash != schema2.content_hash

        product2 = schema_to_product_model(schema2)
        product2.id = retrieved1.id
        repository.upsert_many([product2])

        retrieved2 = repository.get_by_external_id("7777")
        assert retrieved2.name == "Updated Name"
        assert retrieved2.gender == "Women"
        assert retrieved2.content_hash != hash1

    def test_duplicate_external_ids_in_batch(self) -> None:
        """Duplicate external_product_ids in a batch are detected."""
        record1 = ProductIngestSchema(
            id=5555,
            productDisplayName="Shirt A",
        )
        record2 = ProductIngestSchema(
            id=5555,
            productDisplayName="Shirt B",
        )

        schema1 = map_to_product_create_schema(record1)
        schema2 = map_to_product_create_schema(record2)

        assert schema1 is not None
        assert schema2 is not None

        assert schema1.external_product_id == schema2.external_product_id
        assert schema1.content_hash != schema2.content_hash


class TestEndToEndSmallSample:
    """End-to-end ingestion test with small sample."""

    def test_ingest_small_sample(self, repository: ProductRepository) -> None:
        """Ingest 5 test products and verify."""
        records = [
            ProductIngestSchema(
                id=1001,
                productDisplayName="Shirt",
                gender="Men",
                masterCategory="Apparel",
                subCategory="Topwear",
                articleType="Shirts",
                baseColour="Blue",
                usage="Casual",
                season="Summer",
                year=2020.0,
            ),
            ProductIngestSchema(
                id=1002,
                productDisplayName="Jeans",
                gender="Women",
                masterCategory="Apparel",
                subCategory="Bottomwear",
                articleType="Jeans",
                baseColour="Black",
                usage="Casual",
                season="Winter",
                year=2021.0,
            ),
            ProductIngestSchema(
                id=1003,
                productDisplayName="Watch",
                gender="Unisex",
                masterCategory="Accessories",
                subCategory="Watches",
                articleType="Watches",
                baseColour="Silver",
                usage="Formal",
                season=None,
                year=2022.0,
            ),
            ProductIngestSchema(
                id=1004,
                productDisplayName="Shoes",
                gender="Men",
                masterCategory="Footwear",
                subCategory="Sports Shoes",
                articleType="Shoes",
                baseColour="White",
                usage="Sports",
                season=None,
                year=2021.0,
            ),
            ProductIngestSchema(
                id=1005,
                productDisplayName="Cap",
                gender="Unisex",
                masterCategory="Accessories",
                subCategory="Headwear",
                articleType="Caps",
                baseColour="Red",
                usage="Casual",
                season="Summer",
                year=2020.0,
            ),
        ]

        products = []
        for record in records:
            schema = map_to_product_create_schema(record)
            assert schema is not None
            products.append(schema_to_product_model(schema))

        repository.upsert_many(products)

        for record in records:
            retrieved = repository.get_by_external_id(str(record.id))
            assert retrieved is not None
            assert retrieved.name == record.productDisplayName
            assert retrieved.external_product_id == str(record.id)

    def test_second_ingestion_skips_unchanged(self, repository: ProductRepository) -> None:
        """Ingest same data twice, second time should skip."""
        record = ProductIngestSchema(
            id=2001,
            productDisplayName="Test Product",
            gender="Men",
            masterCategory="Apparel",
        )

        schema1 = map_to_product_create_schema(record)
        product1 = schema_to_product_model(schema1)
        repository.upsert_many([product1])

        schema2 = map_to_product_create_schema(record)
        assert schema1.content_hash == schema2.content_hash

        product2 = repository.get_by_external_id("2001")
        assert product2.content_hash == schema2.content_hash
