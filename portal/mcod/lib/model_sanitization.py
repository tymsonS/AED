import html
from typing import Dict, List, Union

import nh3
from ckeditor_uploader.fields import RichTextUploadingField as BaseRichTextUploadingField
from django.contrib.postgres.fields import JSONField
from django.contrib.postgres.fields.jsonb import JsonAdapter
from django.db import models
from modeltrans.fields import TranslationField


def sanitize_html(html_content: str, strip_comments: bool = False) -> str:
    """
    Sanitize HTML content using explicit allowlists for tags, attributes,
    URL schemes, and inline CSS properties.

    Before sanitization, one layer of HTML entities is decoded so that encoded
    HTML tags are parsed and sanitized instead of being treated as plain text.
    Disallowed tags, attributes, URL schemes, and CSS properties are removed.
    Text content inside disallowed elements may be preserved as non-executable text.

    Args:
        html_content: The HTML content to sanitize.
        strip_comments: Whether HTML comments should be removed.

    Returns:
        Sanitized HTML content.

    Allowed tags:
        a, abbr, acronym, address, b, br, blockquote, code, div, em,
        h1, h2, h3, h4, h5, h6, hr, i, img, li, ol, p, pre, span,
        strong, table, caption, tbody, tr, td, ul.

    Allowed attributes:
        - Global: style.
        - a: href, title, target.
        - abbr and acronym: title.
        - img: src, alt, title, width, height.
        - table: align, border, caption, cellpadding, cellspacing, dir,
          width, height, id, summary.

    Allowed URL schemes:
        http, https.

    Example:
        input_html = (
            '&lt;img src=x '
            'onerror=&quot;alert(document.cookie)&quot;&gt;'
        )

        sanitize_html(input_html)
        # Returns: '<img src="x">'
    """
    allowed_tags = {
        "a",
        "abbr",
        "acronym",
        "address",
        "b",
        "br",
        "blockquote",
        "code",
        "div",
        "em",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "hr",
        "i",
        "img",
        "li",
        "ol",
        "p",
        "pre",
        "span",
        "strong",
        "table",
        "caption",
        "tbody",
        "tr",
        "td",
        "ul",
    }
    allowed_attributes = {
        "*": {"style"},
        "a": {"href", "title", "target"},
        "abbr": {"title"},
        "acronym": {"title"},
        "img": {"src", "alt", "title", "width", "height"},
        "table": {
            "align",
            "border",
            "caption",
            "cellpadding",
            "cellspacing",
            "dir",
            "width",
            "height",
            "id",
            "summary",
        },
    }

    allowed_styles = {
        "color",
        "background-color",
        "font-family",
        "font-weight",
        "font-size",
        "width",
        "height",
        "text-align",
        "border",
        "border-width",
        "border-style",
        "border-color",
        "border-radius",
        "padding",
        "padding-top",
        "padding-right",
        "padding-bottom",
        "padding-left",
        "margin",
        "margin-top",
        "margin-right",
        "margin-bottom",
        "margin-left",
        "text-decoration",
        "line-height",
        "font-style",
        "font-variant",
        "letter-spacing",
        "word-spacing",
        "text-transform",
        "white-space",
        "vertical-align",
        "list-style-type",
        "list-style-position",
        "list-style-image",
    }

    cleaner = nh3.Cleaner(
        tags=allowed_tags,
        attributes=allowed_attributes,
        clean_content_tags=set(),
        filter_style_properties=allowed_styles,
        url_schemes={"http", "https"},
        strip_comments=strip_comments,
        link_rel="noopener",
    )

    decoded_html = html.unescape(html_content)

    return cleaner.clean(decoded_html)


class SanitizedCharField(models.CharField):
    def get_prep_value(self, value: str):
        value = super().get_prep_value(value)
        if isinstance(value, str):
            return sanitize_html(value)
        return value


class SanitizedRichTextUploadingField(BaseRichTextUploadingField):
    def get_prep_value(self, value: str):
        value = super().get_prep_value(value)
        if isinstance(value, str):
            return sanitize_html(value)
        return value


class SanitizedTextField(models.TextField):
    def get_prep_value(self, value: str):
        value = super().get_prep_value(value)
        if isinstance(value, str):
            return sanitize_html(value)
        return value


class SanitizedJSONField(JSONField):
    """
    Overloads the `get_prep_value` method of the `JSONField` class to sanitize JSON fields specific to
    this project's forms. Depending on the instance type after unpacking (dictionary or list), sanitizes a specific
    field value. The class is not for general use and its use must be tested.
    """

    def get_prep_value(self, value: Union[Dict[str, str], List[Dict[str, str]]]):
        value = super().get_prep_value(value)
        if isinstance(value, JsonAdapter):
            value = value.adapted

        if isinstance(value, dict):
            return self._sanitize_dict(value)
        elif isinstance(value, list):
            return self._sanitize_list(value)
        return value

    def _sanitize_dict(self, value: Dict[str, str]) -> JsonAdapter:
        """
        Sanitizes a dictionary by sanitizing both keys and values.
        """
        sanitized_value = {sanitize_html(key): sanitize_html(val) for key, val in value.items()}
        return JsonAdapter(sanitized_value, encoder=self.encoder)

    def _sanitize_list(self, value: List[Union[str, Dict[str, str]]]) -> JsonAdapter:
        """
        Sanitizes a list by sanitizing each item. If an item is a dictionary, it sanitizes the key-value pairs.
        """
        sanitized_list = []
        for item in value:
            if isinstance(item, dict):
                sanitized_item = {key: sanitize_html(val) if val is not None else None for key, val in item.items()}
                sanitized_list.append(sanitized_item)
            else:
                sanitized_list.append(sanitize_html(item))
        return JsonAdapter(sanitized_list, encoder=self.encoder)


class SanitizedTranslationField(TranslationField):
    def get_prep_value(self, value: Dict[str, str]):
        value = super().get_prep_value(value)
        if isinstance(value, JsonAdapter):
            value = value.adapted

        if isinstance(value, dict):
            return self._sanitize_dict(value)
        return value

    def _sanitize_dict(self, value: Dict[str, str]) -> JsonAdapter:
        """
        Sanitizes a dictionary by sanitizing the values of the key-value pairs.
        If a value is `None`, it is preserved as `None`. The keys are left unchanged.
        """
        sanitized_value = {key: sanitize_html(val) if val is not None else None for key, val in value.items()}
        return JsonAdapter(sanitized_value, encoder=self.encoder)
