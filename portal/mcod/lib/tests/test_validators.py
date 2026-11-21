from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from django.core.exceptions import ValidationError
from django.core.files import File

from mcod.lib.field_validators import validate_uploaded_file

ALLOWED = {
    "pdf": frozenset({"application/pdf"}),
    "png": frozenset({"image/png"}),
}
MAX_SIZE = 1024 * 1024  # 1MB


def make_file(name: str, content: bytes = b"x" * 100) -> File:
    f = BytesIO(content)
    f.name = name
    mock_file = MagicMock(spec=File)
    mock_file.name = name
    mock_file.size = len(content)
    mock_file.read.return_value = content[:2048]
    mock_file.seek.return_value = None
    return mock_file


class TestValidateUploadedFile:

    def test_valid_file_passes(self):
        f = make_file("document.pdf")
        with patch("mcod.lib.field_validators.magic.from_buffer", return_value="application/pdf"):
            # should not raise
            validate_uploaded_file(f, ALLOWED, MAX_SIZE)

    def test_extension_case_insensitive(self):
        f = make_file("document.PDF")
        with patch("mcod.lib.field_validators.magic.from_buffer", return_value="application/pdf"):
            validate_uploaded_file(f, ALLOWED, MAX_SIZE)

    def test_file_too_large(self):
        f = make_file("big.pdf", content=b"x" * (MAX_SIZE + 1))
        with pytest.raises(ValidationError) as err:
            validate_uploaded_file(f, ALLOWED, MAX_SIZE)
        assert f"Plik jest za duży, maksymalny rozmiar to {MAX_SIZE} bajtów." in err.value.messages

    def test_empty_sting_as_filename(self):
        f = make_file("     ")
        with pytest.raises(ValidationError) as err:
            validate_uploaded_file(f, ALLOWED, MAX_SIZE)
        assert "Wczytany plik nie ma nazwy." in err.value.messages

    def test_not_allowed_extension(self):
        f = make_file("file.exe")
        with pytest.raises(ValidationError) as err:
            validate_uploaded_file(f, ALLOWED, MAX_SIZE)
        assert "Niepoprawne rozszerzenie pliku: exe." in err.value.messages

    def test_empty_extension(self):
        f = make_file("no_extension_file")
        with pytest.raises(ValidationError) as err:
            validate_uploaded_file(f, ALLOWED, MAX_SIZE)
        assert "Plik no_extension_file nie posiada rozszerzenia." in err.value.messages

    def test_extension_not_match_mimetype(self):
        f = make_file("image.png")
        with patch("mcod.lib.field_validators.magic.from_buffer", return_value="application/pdf"):
            with pytest.raises(ValidationError) as err:
                validate_uploaded_file(f, ALLOWED, MAX_SIZE)
            assert "Niepoprawny format pliku" in err.value.messages
