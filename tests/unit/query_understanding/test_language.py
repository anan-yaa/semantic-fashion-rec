"""Unit tests for query language detection."""
import json
from pathlib import Path

import pytest

from app.services.query_understanding.language import detect_language, is_english

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize(
    "query, expected",
    [
        ("vestido rojo para mujer", "Spanish"),
        ("chaqueta de invierno para hombre", "Spanish"),
        ("atuendo playero", "Spanish"),
        ("gafas de sol", "Spanish"),
        ("robe rouge pour femme", "French"),
        ("sac à main noir", "French"),
        ("नीली शर्ट", "Hindi"),
        ("连衣裙", "non-English"),
    ],
)
def test_non_english_queries(query, expected):
    assert detect_language(query) == expected


@pytest.mark.parametrize(
    "query",
    ["summer sandals", "beige sandals", "kurta for men", "maroon saree", "polo t-shirt", "pink innerwear", "jeans",
     "I need an outfit to go to the beach this summer"],
)
def test_short_english_queries_stay_english(query):
    """These were misread as German, Italian or Portuguese by detectors with more languages."""
    assert is_english(query)


def test_every_english_eval_query_is_english():
    judgments = json.loads((ROOT / "evals/ground_truth/ground_truth_v2_real.json").read_text())["judgments"]
    english = [j["query"] for j in judgments if j["query"].isascii()]
    assert [q for q in english if not is_english(q)] == []
