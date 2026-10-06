"""Load HuggingFace fashion dataset without loading image data."""

from datasets import Dataset


def load_dataset_from_cache() -> Dataset:
    """
    Load HuggingFace dataset from local cache.

    Removes image column to avoid loading into memory.

    Returns:
        Dataset with only metadata columns.

    Raises:
        Exception: If dataset cannot be loaded.
    """
    from datasets import load_dataset

    ds = load_dataset(
        "HEBA2002/fashion-product-images-small",
        split="train",
        trust_remote_code=False,
    )

    # Select only metadata columns, ignore image
    cols_to_keep = [
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
    ]
    ds = ds.select_columns(cols_to_keep)
    return ds


def load_dataset_from_path(path: str) -> Dataset:
    """
    Load HuggingFace dataset from a specific path.

    Args:
        path: Path to dataset directory.

    Returns:
        Dataset with only metadata columns.

    Raises:
        Exception: If dataset cannot be loaded from path.
    """
    from datasets import load_dataset

    ds = load_dataset(path, split="train", trust_remote_code=False)

    # Select only metadata columns, ignore image
    cols_to_keep = [
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
    ]
    ds = ds.select_columns(cols_to_keep)
    return ds
