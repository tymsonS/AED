from django.conf import settings

from mcod.academy.constants import (
    ALLOWED_COURSE_FILE_EXTENSIONS,
    ALLOWED_COURSE_FILE_EXTENSIONS_MIME_TYPES,
)


class TestBuildAllowedCourseFileMimeTypes:

    def test_all_course_file_extensions_included(self):
        for ext in ALLOWED_COURSE_FILE_EXTENSIONS:
            assert ext in ALLOWED_COURSE_FILE_EXTENSIONS_MIME_TYPES
            if ext in settings.EXTENSION_TO_MIME_TYPE_MAP:
                assert ALLOWED_COURSE_FILE_EXTENSIONS_MIME_TYPES[ext] == settings.EXTENSION_TO_MIME_TYPE_MAP[ext]

    def test_all_course_file_extensions_consistent_with_requirements(self):
        required_extensions = frozenset(
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

        for ext in required_extensions:
            assert (
                ext in ALLOWED_COURSE_FILE_EXTENSIONS_MIME_TYPES
            ), f"Extension '{ext}' is missing from ALLOWED_COURSE_FILE_EXTENSIONS_MIME_TYPES"
