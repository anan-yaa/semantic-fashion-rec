"""Unit tests for dataset loading."""

from app.services.ingestion.loader import load_dataset_from_cache


class TestLoadDataset:
    """Test dataset loading."""

    def test_load_dataset_from_cache_returns_dataset(self):
        """Loading from cache returns a Dataset object."""
        ds = load_dataset_from_cache()
        assert ds is not None
        assert len(ds) > 0

    def test_load_dataset_has_required_columns(self):
        """Loaded dataset has all required metadata columns."""
        ds = load_dataset_from_cache()
        required_cols = {
            "id",
            "gender",
            "masterCategory",
            "subCategory",
            "articleType",
            "baseColour",
            "season",
            "year",
            "usage",
            "productDisplayName",
        }
        assert set(ds.column_names) == required_cols

    def test_load_dataset_no_image_column(self):
        """Loaded dataset does not include image column."""
        ds = load_dataset_from_cache()
        assert "image" not in ds.column_names

    def test_load_dataset_records_accessible(self):
        """Records can be accessed as dictionaries."""
        ds = load_dataset_from_cache()
        record = ds[0]
        assert isinstance(record, dict)
        assert "id" in record
        assert "productDisplayName" in record

    def test_load_dataset_correct_size(self):
        """Loaded dataset has expected number of products."""
        ds = load_dataset_from_cache()
        # Fashion dataset has 44,072 products
        assert len(ds) == 44072
