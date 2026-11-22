from typing import Dict, List, Type, Union

import pytest
from django.contrib.postgres.fields.jsonb import JsonAdapter
from django.utils.html import format_html

from mcod.lib.model_sanitization import (
    SanitizedCharField,
    SanitizedJSONField,
    SanitizedRichTextUploadingField,
    SanitizedTextField,
    SanitizedTranslationField,
    sanitize_html,
)
from mcod.lib.tests.xss_sanitization_cases import XSS_SANITIZATION_CASES
from mcod.lib.utils import (
    capitalize_first_character,
    escape_braces_and_format_html,
    get_file_extensions_no_dot,
)


class TestFormatHTML:
    """
    Tests for HTML formatting functions, specifically examining behavior when
    processing curly braces.

    This test class includes methods to test two different behaviors:
    1. The newly implemented function `escape_braces_and_format_html`,
    which is supposed to correctly escape curly braces to prevent them from
    being treated as placeholders in a formatting string.
    2. The standard Django `format_html` function, which throws exceptions
    or modifies the input text when it contains curly braces that might be
    mistaken for format specifiers.
    """

    @pytest.mark.parametrize(
        "text", ["{text", "{{ text", "test {text}", "}{", "{}", "test }} text", "text}", "<div>{text in braces}</div>"]
    )
    def test_escape_braces_and_format_html(self, text: str):
        formatted_text: str = escape_braces_and_format_html(text)
        assert formatted_text == text

    @pytest.mark.parametrize("text", ["{{ text", "test }} text"])
    def test_format_html_change_text_with_escaped_braces(self, text: str):
        assert format_html(text) != text

    @pytest.mark.parametrize("text", ["{text", "test {text}", "}{", "{}", "text}"])
    def test_format_html_raise_exc_for_unescaped_braces(self, text: str):
        with pytest.raises((KeyError, ValueError, IndexError)):
            format_html(text)


@pytest.mark.parametrize(
    ("input_text", "expected_text"),
    [
        ("some string", "Some string"),
        ("some string. another string", "Some string. another string"),
        ("some String", "Some String"),
        ("Some String", "Some String"),
        ("underscore_string", "Underscore_string"),
        ("1 Some String", "1 Some String"),
        (" Some String", " Some String"),
        ("", ""),
        (" ", " "),
    ],
)
def test_capitalize_first_character(input_text: str, expected_text: str):
    assert expected_text == capitalize_first_character(input_text)


class TestXssSanitizer:
    def test_sanitize_html_decodes_entities_before_removing_unsafe_attributes(self):
        xss_event = "onerror"
        xss_script = "alert(document.cookie)"
        payload_with_xss = f"&lt;img src=x {xss_event}=&quot;{xss_script}&quot;&gt;"

        sanitized_payload = sanitize_html(payload_with_xss)

        assert sanitized_payload == '<img src="x">'
        assert xss_event not in sanitized_payload
        assert xss_script not in sanitized_payload

    @pytest.mark.parametrize("dangerous_html_tags, expected_output", XSS_SANITIZATION_CASES)
    def test_input_dangerous_html_tags(self, dangerous_html_tags: str, expected_output: str):
        assert sanitize_html(dangerous_html_tags) == expected_output


test_data_all_fields = [
    ("<script>alert('XSS');</script><p>Hello World</p>", "alert('XSS');<p>Hello World</p>"),
    ("<b>Bold Text</b>", "<b>Bold Text</b>"),
    ("No HTML", "No HTML"),
    ("<script>console.log('test');</script>", "console.log('test');"),
    (None, None),
]

test_classes = [SanitizedCharField, SanitizedRichTextUploadingField, SanitizedTextField]


@pytest.mark.parametrize("cls", test_classes)
@pytest.mark.parametrize("input_value, expected_output", test_data_all_fields)
def test_sanitize_for_all_fields(cls: Type, input_value: str, expected_output: str) -> None:
    """Tests HTML sanitization features against malicious XSS, specifically examining behavior when
    input is String"""
    instance = cls()
    sanitized_value = instance.get_prep_value(input_value)
    assert sanitized_value == expected_output


test_data_json_field = [
    ({"<script>key</script>": "<script>alert('XSS');</script>value"}, {"key": "alert('XSS');value"}),
    ([{"title": "<script>Title</script>", "url": "<script>URL</script>"}], [{"title": "Title", "url": "URL"}]),
    (["<b>Bold</b>", {"title": "<script>Another Title</script>"}], ["<b>Bold</b>", {"title": "Another Title"}]),
    ([], []),
    (None, None),
]


@pytest.mark.parametrize("input_value, expected_output", test_data_json_field)
def test_sanitize_json_field(
    input_value: Union[Dict[str, str], List[Dict[str, str]]], expected_output: Union[Dict[str, str], List[Dict[str, str]]]
) -> None:
    """Tests HTML sanitization features against malicious XSS, specifically examining behavior when
    input is JSONField."""
    instance = SanitizedJSONField()
    sanitized_value = instance.get_prep_value(input_value)
    if isinstance(sanitized_value, JsonAdapter):
        sanitized_value = sanitized_value.adapted
    assert sanitized_value == expected_output


test_data_translation_field = [
    ({"<script>title_en</script>": "<script>alert('XSS');</script>value"}, {"<script>title_en</script>": "alert('XSS');value"}),
    ({"title_en": None, "title_pl": "<script>alert('Hello');</script>"}, {"title_en": None, "title_pl": "alert('Hello');"}),
    ({}, {}),
    (None, None),
]


@pytest.mark.parametrize("input_value, expected_output", test_data_translation_field)
def test_sanitize_translation_field(input_value: Dict[str, str], expected_output: Dict[str, str]) -> None:
    """Tests HTML sanitization features against malicious XSS, specifically examining behavior when
    the input is TranslationField"""
    instance = SanitizedTranslationField()
    sanitized_value = instance.get_prep_value(input_value)
    if isinstance(sanitized_value, JsonAdapter):
        sanitized_value = sanitized_value.adapted
    assert sanitized_value == expected_output


@pytest.mark.parametrize(
    "filenames, expected_extensions",
    (
        (["1.csv", "1.", "1"], ["csv"]),
        (["1.csv", "1.xml", "1.xml.gpg"], ["csv", "xml", "gpg"]),
    ),
)
def test_get_file_extensions_no_dot(filenames: List[str], expected_extensions: List[str]) -> None:
    assert get_file_extensions_no_dot(filenames) == expected_extensions
