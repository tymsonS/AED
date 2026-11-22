import pytest
from django.core.exceptions import ValidationError

from mcod.core.model_validators import css_selector_validator, illegal_character_validator


@pytest.mark.parametrize(
    "char",
    [
        "&",
        "<",
        ">",
        '"',
        "'",
        "-",
        "*",
    ],
)
def test_illegal_character_validator_allows_chars(char):
    """Validator should NOT raise for allowed characters.

    Given the "no unescape" policy, numeric entities (e.g., '&#x26;', '&#x02;')
    are treated as literal text and should pass. Characters like '&', '<', '>'
    are allowed as input because downstream XML writers will escape them.
    """
    illegal_character_validator(f"ok{char}ok")


@pytest.mark.parametrize(
    "char",
    [
        # --- DISALLOWED in XML 1.0 (Fifth Edition) ---
        "\x00",  # null character (NUL)
        "\x01",
        "\x02",  # Start of Text — control character
        "\x03",
        "\x0B",  # vertical tab
        "\x0C",  # form feed (page break)
        "\uD800",  # lone high surrogate (disallowed)
        "\uDFFF",  # lone low surrogate (disallowed)
        "\uFFFE",  # non-character (disallowed in XML)
        "\uFFFF",  # non-character (disallowed in XML)
    ],
)
def test_illegal_character_validator_rejects_illegal_chars(char):
    """Validator MUST raise ValidationError for illegal XML 1.0 characters.

    This includes all disallowed C0 control characters (except TAB/LF/CR),
    surrogate code points, and non-characters like U+FFFE/U+FFFF.
    """
    with pytest.raises(ValidationError):
        illegal_character_validator(f"bad{char}bad")


@pytest.mark.parametrize(
    "selector",
    [
        "div > p",
        "main .content a[href^='https']",
        "#guide-item, .guide-item",
        "ul li:first-child",
        "#main-footer .row > .col-lg-3:nth-child(4)",
    ],
)
def test_css_selector_validator_accepts_valid_selectors(selector):
    assert css_selector_validator(selector) is None


@pytest.mark.parametrize(
    "selector",
    [
        "<script>alert(1)</script>",
        "<img src=x onerror=alert(1)>",
        "div; alert(1)",
        "div >> p",
    ],
)
def test_css_selector_validator_rejects_markup_and_invalid_css(selector):
    with pytest.raises(ValidationError) as e:
        css_selector_validator(selector)
    assert e.value.message == "Proszę wprowadzić prawidłowy selektor CSS."
