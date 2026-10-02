"""Unit tests for record mapping."""

from app.schemas.product import ProductIngestSchema
from app.services.ingestion.mapper import (
    build_search_text,
    map_record_to_product_schema,
)


class TestBuildSearchText:
    """Test search text construction."""

    def test_all_fields(self):
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
        result = build_search_text(record)
        assert "blue shirt" in result
        assert "men" in result
        assert "apparel" in result
        assert "topwear" in result
        assert "shirts" in result
        assert "blue" in result
        assert "casual" in result
        assert "summer" in result

    def test_normalizes_fields(self):
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

    def test_skips_none_values(self):
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

    def test_field_order_deterministic(self):
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
        # Must match the fixed order in the function
        assert result == "a b c d e f g h"

    def test_deterministic(self):
        record = ProductIngestSchema(
            id=1,
            productDisplayName="Shirt",
            gender="Men",
            masterCategory="Apparel",
        )
        result1 = build_search_text(record)
        result2 = build_search_text(record)
        assert result1 == result2


class TestMapRecordToProductSchema:
    """Test mapping HF record to internal schema."""

    def test_valid_record_mapping(self):
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
        schema = map_record_to_product_schema(record)
        assert schema is not None
        assert schema.external_product_id == "12345"
        assert schema.name == "Blue Shirt"
        assert schema.category == "Apparel"
        assert schema.subcategory == "Topwear"
        assert schema.gender == "Men"
        assert schema.color == "Blue"
        assert schema.style == "Casual"
        assert schema.season == "Summer"

    def test_null_fields(self):
        record = ProductIngestSchema(
            id=1,
            productDisplayName="Shirt",
            gender="Men",
        )
        schema = map_record_to_product_schema(record)
        assert schema.brand is None
        assert schema.material is None
        assert schema.price is None

    def test_currency_default(self):
        record = ProductIngestSchema(
            id=1,
            productDisplayName="Shirt",
        )
        schema = map_record_to_product_schema(record)
        assert schema.currency == "USD"

    def test_availability_default(self):
        record = ProductIngestSchema(
            id=1,
            productDisplayName="Shirt",
        )
        schema = map_record_to_product_schema(record)
        assert schema.availability is True

    def test_attributes_preserve_article_type_and_year(self):
        record = ProductIngestSchema(
            id=1,
            productDisplayName="Shirt",
            articleType="Shirts",
            year=2021.0,
        )
        schema = map_record_to_product_schema(record)
        assert schema.attributes is not None
        assert schema.attributes["articleType"] == "Shirts"
        assert schema.attributes["year"] == 2021.0

    def test_attributes_empty_when_no_extra_fields(self):
        record = ProductIngestSchema(
            id=1,
            productDisplayName="Shirt",
            articleType=None,
            year=None,
        )
        schema = map_record_to_product_schema(record)
        assert schema.attributes is None

    def test_missing_product_display_name(self):
        record = ProductIngestSchema(
            id=1,
            productDisplayName=None,
        )
        schema = map_record_to_product_schema(record)
        assert schema is None

    def test_empty_product_display_name(self):
        record = ProductIngestSchema(
            id=1,
            productDisplayName="",
        )
        schema = map_record_to_product_schema(record)
        assert schema is None

    def test_search_text_set(self):
        record = ProductIngestSchema(
            id=1,
            productDisplayName="Blue Shirt",
            gender="Men",
        )
        schema = map_record_to_product_schema(record)
        assert schema.search_text is not None
        assert "blue shirt" in schema.search_text
        assert "men" in schema.search_text

    def test_content_hash_set_and_valid(self):
        record = ProductIngestSchema(
            id=1,
            productDisplayName="Shirt",
        )
        schema = map_record_to_product_schema(record)
        assert schema.content_hash is not None
        assert len(schema.content_hash) == 64  # SHA256 hex digest

    def test_uuid_generated(self):
        record = ProductIngestSchema(
            id=1,
            productDisplayName="Shirt",
        )
        schema1 = map_record_to_product_schema(record)
        schema2 = map_record_to_product_schema(record)
        # Each mapping should generate different UUIDs
        assert schema1.id != schema2.id
        assert len(schema1.id) == 36  # UUID string length
