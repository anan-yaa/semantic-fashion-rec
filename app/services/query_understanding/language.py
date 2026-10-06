"""Detect a search query's language, to decide whether it needs translating.

A 1B LLM can't reliably tell Spanish or French from English (Gemma 3 1B
labelled every Spanish and French test query as English), so a dedicated
detector decides instead. Supported: English, Spanish, French, German, Italian,
Portuguese (told apart statistically) and Hindi, Arabic, Chinese, Russian (told
apart by script). Anything else in another script is "non-English" and still
sent for translation; other Latin-script languages are read as English.

Adding Latin-script languages makes short English queries more likely to be
misread ("summer sandals" was labelled German with 7 languages), so a query
only counts as non-English when that is clearly more likely than English, and
single words stay English: English fashion vocabulary is full of loanwords
("poncho", "mules", "bandana"), and a foreign single word searched as written
still works through the multilingual embedding model.
"""
from functools import lru_cache

from lingua import Language, LanguageDetectorBuilder

ENGLISH = "English"
_LATIN_LANGUAGES = [
    Language.ENGLISH, Language.SPANISH, Language.FRENCH, Language.GERMAN, Language.ITALIAN, Language.PORTUGUESE,
]
_NAMES = {
    Language.ENGLISH: ENGLISH, Language.SPANISH: "Spanish", Language.FRENCH: "French",
    Language.GERMAN: "German", Language.ITALIAN: "Italian", Language.PORTUGUESE: "Portuguese",
}
# How much more likely than English another language must be to count.
_MARGIN = 0.2

# Unicode ranges of the non-Latin scripts told apart by script.
_KANA = (0x3040, 0x30FF)
_SCRIPTS = {
    "Hindi": [(0x0900, 0x097F)],
    "Arabic": [(0x0600, 0x06FF), (0x0750, 0x077F), (0xFB50, 0xFDFF), (0xFE70, 0xFEFF)],
    "Russian": [(0x0400, 0x04FF)],
    "Chinese": [(0x3400, 0x4DBF), (0x4E00, 0x9FFF)],
}


@lru_cache(maxsize=1)
def _detector():
    return LanguageDetectorBuilder.from_languages(*_LATIN_LANGUAGES).build()


def _in(ranges, char: str) -> bool:
    return any(low <= ord(char) <= high for low, high in ranges)


def _script_language(query: str):
    letters = [c for c in query if c.isalpha() and ord(c) > 0x024F]
    if not letters:
        return None
    if any(_in([_KANA], c) for c in letters):
        return "non-English"  # Japanese shares ideographs with Chinese; it isn't a supported language
    counts = {name: sum(_in(ranges, c) for c in letters) for name, ranges in _SCRIPTS.items()}
    best = max(counts, key=counts.get)
    return best if counts[best] else "non-English"  # another script; the LLM is still asked to translate


def detect_language(query: str) -> str:
    """'English', 'Spanish', 'French', 'German', 'Italian', 'Portuguese', 'Hindi', 'Arabic', 'Chinese',
    'Russian', or 'non-English' (other scripts)."""
    by_script = _script_language(query)
    if by_script:
        return by_script
    if len(query.split()) < 2:
        return ENGLISH
    values = _detector().compute_language_confidence_values(query)
    best = values[0]
    english = next(v.value for v in values if v.language == Language.ENGLISH)
    if best.language == Language.ENGLISH or best.value - english < _MARGIN:
        return ENGLISH
    return _NAMES.get(best.language, ENGLISH)


def is_english(query: str) -> bool:
    return detect_language(query) == ENGLISH
