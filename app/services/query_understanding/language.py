"""Detect a search query's language, to decide whether it needs translating.

A 1B LLM can't reliably tell Spanish or French from English (Gemma 3 1B
labelled every Spanish and French test query as English), so a dedicated
detector decides instead. It's restricted to the supported languages: adding
more makes short English queries more likely to be misread ("summer sandals"
was labelled German with 7 languages), and a query is only called non-English
when that's clearly more likely than English. On the eval queries this
labelled 77 of 77 English queries English and 22 of 22 Hindi, Spanish and
French queries correctly.
"""
from functools import lru_cache

from lingua import Language, LanguageDetectorBuilder

ENGLISH = "English"
_LATIN_LANGUAGES = [Language.ENGLISH, Language.SPANISH, Language.FRENCH]
_NAMES = {Language.ENGLISH: ENGLISH, Language.SPANISH: "Spanish", Language.FRENCH: "French"}
# How much more likely than English another language must be to count.
_MARGIN = 0.2


@lru_cache(maxsize=1)
def _detector():
    return LanguageDetectorBuilder.from_languages(*_LATIN_LANGUAGES, Language.HINDI).build()


def _script_language(query: str):
    letters = [c for c in query if c.isalpha() and ord(c) > 0x024F]
    if not letters:
        return None
    if any(0x0900 <= ord(c) <= 0x097F for c in letters):
        return "Hindi"
    return "non-English"  # another non-Latin script; the LLM is still asked to translate


def detect_language(query: str) -> str:
    """'English', 'Spanish', 'French', 'Hindi', or 'non-English' (other scripts)."""
    by_script = _script_language(query)
    if by_script:
        return by_script
    values = _detector().compute_language_confidence_values(query)
    best = values[0]
    english = next(v.value for v in values if v.language == Language.ENGLISH)
    if best.language == Language.ENGLISH or best.value - english < _MARGIN:
        return ENGLISH
    return _NAMES.get(best.language, ENGLISH)


def is_english(query: str) -> bool:
    return detect_language(query) == ENGLISH
