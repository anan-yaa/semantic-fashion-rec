"""Live catalogue facet vocabulary for LLM-inferred search filters.

These are the exact distinct, non-null values of the corresponding Product
columns, queried directly from the database (SELECT DISTINCT <col> FROM
products WHERE <col> IS NOT NULL ORDER BY <col>). Keeping this as a static
list (rather than querying the DB on every request) keeps query understanding
fast and avoids an extra DB round trip on the request path; if the catalogue's
facet values change, regenerate this list the same way.

Only category/gender/color/season are listed: these are the only SearchFilter
fields an LLM could plausibly infer from free text. `availability` is never
inferable from query text and is intentionally excluded.
"""
from typing import Dict, List

CATALOGUE_FACETS: Dict[str, List[str]] = {
    "category": [
        "Accessories",
        "Apparel",
        "Footwear",
        "Free Items",
        "Home",
        "Personal Care",
        "Sporting Goods",
    ],
    "gender": ["Boys", "Girls", "Men", "Unisex", "Women"],
    "color": [
        "Beige",
        "Black",
        "Blue",
        "Bronze",
        "Brown",
        "Burgundy",
        "Charcoal",
        "Coffee Brown",
        "Copper",
        "Cream",
        "Fluorescent Green",
        "Gold",
        "Green",
        "Grey",
        "Grey Melange",
        "Khaki",
        "Lavender",
        "Lime Green",
        "Magenta",
        "Maroon",
        "Mauve",
        "Metallic",
        "Multi",
        "Mushroom Brown",
        "Mustard",
        "Navy Blue",
        "Nude",
        "Off White",
        "Olive",
        "Orange",
        "Peach",
        "Pink",
        "Purple",
        "Red",
        "Rose",
        "Rust",
        "Sea Green",
        "Silver",
        "Skin",
        "Steel",
        "Tan",
        "Taupe",
        "Teal",
        "Turquoise Blue",
        "White",
        "Yellow",
    ],
    "season": ["Fall", "Spring", "Summer", "Winter"],
}
