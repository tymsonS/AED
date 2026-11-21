from typing import Dict, FrozenSet

from django.conf import settings

ALLOWED_COURSE_FILE_EXTENSIONS = frozenset(
    {
        "csv",
        "xlsx",
        "xls",
        "ppt",
        "pptx",
        "pps",
        "doc",
        "docx",
        "odt",
        "ods",
        "odp",
        "pdf",
        "gif",
        "jpeg",
        "jpg",
        "jpe",
        "png",
        "zip",
        "7z",
    }
)


def _build_allowed_course_file_extensions_mime_types() -> Dict[str, FrozenSet[str]]:
    """
    Build a dictionary mapping allowed course file extensions to their corresponding MIME types.
    The MIME types are retrieved from the Django settings.
    """

    # Create a dictionary mapping each allowed extension to its MIME types
    allowed_extensions_mime_types = {
        ext: settings.EXTENSION_TO_MIME_TYPE_MAP[ext]
        for ext in ALLOWED_COURSE_FILE_EXTENSIONS
        if ext in settings.EXTENSION_TO_MIME_TYPE_MAP
    }

    # Add the MIME type for 7z files separately - it is not included in the settings mapping
    # and required by Business OTD-1752
    if "7z" not in allowed_extensions_mime_types:
        allowed_extensions_mime_types["7z"] = frozenset({"application/x-7z-compressed"})

    return allowed_extensions_mime_types


ALLOWED_COURSE_FILE_EXTENSIONS_MIME_TYPES = _build_allowed_course_file_extensions_mime_types()
