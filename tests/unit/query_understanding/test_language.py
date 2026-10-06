"""Unit tests for query language detection (10 languages)."""
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
        ("rotes Kleid für Frauen", "German"),
        ("Wintermantel aus Wolle", "German"),
        ("vestito rosso da donna", "Italian"),
        ("scarpe da corsa comode", "Italian"),
        ("vestido vermelho feminino", "Portuguese"),
        ("óculos de sol para o verão", "Portuguese"),
        ("नीली शर्ट", "Hindi"),
        ("فستان أحمر للنساء", "Arabic"),
        ("连衣裙", "Chinese"),
        ("女士红色连衣裙", "Chinese"),
        ("красное платье для женщин", "Russian"),
    ],
)
def test_supported_languages(query, expected):
    assert detect_language(query) == expected


@pytest.mark.parametrize("query", ["黒いジャケット", "검은색 가죽 재킷", "கருப்பு சட்டை"])
def test_other_scripts_are_non_english_and_still_translated(query):
    """Japanese, Korean and Tamil aren't supported by name, but they're still sent for translation."""
    assert detect_language(query) == "non-English"


def test_mixed_script_query_follows_the_dominant_script():
    assert detect_language("Nike 运动鞋 男士") == "Chinese"


@pytest.mark.parametrize("query", ["poncho", "mules", "sombrero", "bandana", "vestido", "Kleid"])
def test_single_words_stay_english(query):
    """English fashion vocabulary is full of loanwords; a foreign single word is searched as written."""
    assert is_english(query)


@pytest.mark.parametrize(
    "query",
    ["summer sandals", "kurta for men", "maroon saree", "polo t-shirt", "pink innerwear", "jeans",
     "I need an outfit to go to the beach this summer", "anarkali suit for women", "palazzo pants for women",
     "kurta pajama for wedding", "nehru jacket for men", "dhoti kurta set", "lehenga choli", "fedora hat"],
)
def test_short_english_queries_stay_english(query):
    """These were misread as German, Italian or Portuguese by detectors with more languages."""
    assert is_english(query)


@pytest.mark.xfail(strict=True, reason="lingua reads 'beige sandals' as German (confidence 0.75); no margin separates it "
                                       "from real German queries")
def test_beige_sandals_known_misread():
    assert is_english("beige sandals")


@pytest.mark.xfail(strict=True, reason="French scores 0.30 vs English <0.17, just under the 0.2 margin; lowering the margin "
                                       "would misread English queries such as 'lehenga choli' and 'summer topwear for men'")
def test_veste_en_cuir_marron_known_misread():
    assert detect_language("veste en cuir marron") == "French"


def test_every_english_eval_query_is_english():
    judgments = json.loads((ROOT / "evals/ground_truth/ground_truth_v2_real.json").read_text())["judgments"]
    english = [j["query"] for j in judgments if j["query"].isascii() and j["query"] != "beige sandals"]
    assert [q for q in english if not is_english(q)] == []


def _labelled_rows():
    rows = []
    for name in ("language_detection_v1.json", "language_detection_holdout_v1.json"):
        rows += json.loads((ROOT / "evals/queries" / name).read_text())["rows"]
    return rows


def test_each_supported_language_is_detected_in_the_labelled_sets():
    """At least 90% per non-English language (known misreads aside), and at most one distinct English query misread."""
    rows = [r for r in _labelled_rows() if r["query"] != "veste en cuir marron"]
    by_language: dict[str, list[bool]] = {}
    english_misreads = set()
    for row in rows:
        ok = detect_language(row["query"]) == row["language"]
        by_language.setdefault(row["language"], []).append(ok)
        if row["language"] == "English" and not ok:
            english_misreads.add(row["query"])

    weak = {lang: sum(r) / len(r) for lang, r in by_language.items() if lang != "English" and sum(r) / len(r) < 0.9}
    assert weak == {}
    assert english_misreads <= {"beige sandals"}
    assert set(by_language) == {
        "English", "German", "Italian", "Portuguese", "Arabic", "Chinese", "Russian", "Spanish", "French", "Hindi",
    }
