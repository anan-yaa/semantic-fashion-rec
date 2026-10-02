"""Unit tests for text normalization."""

from app.services.ingestion.normalizer import normalize_text


class TestNormalizeText:
    """Test text normalization."""

    def test_basic_normalization(self):
        assert normalize_text("Hello World") == "hello world"

    def test_strips_leading_whitespace(self):
        assert normalize_text("  hello") == "hello"

    def test_strips_trailing_whitespace(self):
        assert normalize_text("hello  ") == "hello"

    def test_strips_both_ends(self):
        assert normalize_text("  hello  ") == "hello"

    def test_lowercase_conversion(self):
        assert normalize_text("HELLO") == "hello"
        assert normalize_text("HeLLo") == "hello"

    def test_collapses_repeated_whitespace(self):
        assert normalize_text("hello   world") == "hello world"
        assert normalize_text("hello  \t  world") == "hello world"

    def test_preserves_single_spaces(self):
        assert normalize_text("hello world") == "hello world"

    def test_none_input(self):
        assert normalize_text(None) is None

    def test_empty_string(self):
        assert normalize_text("") is None

    def test_only_whitespace(self):
        assert normalize_text("   ") is None
        assert normalize_text("\t\t") is None

    def test_preserves_word_order(self):
        assert normalize_text("foo bar baz") == "foo bar baz"

    def test_deterministic(self):
        text = "Hello   WORLD"
        result1 = normalize_text(text)
        result2 = normalize_text(text)
        assert result1 == result2
