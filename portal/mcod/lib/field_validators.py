import base64
import binascii
from logging import getLogger
from pathlib import Path
from typing import Dict, FrozenSet

import magic
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.files import File
from django.core.validators import RegexValidator
from django.utils.html import strip_tags
from django.utils.translation import gettext_lazy as _
from marshmallow import ValidationError
from marshmallow.validate import Validator

logger = getLogger("mcod")


class Base64(Validator):
    default_base64_error = "Invalid data format for base64 encoding."
    default_length_error = "Too long data."

    def __init__(self, max_size=None, base64_error=None, length_error=None):
        self.base64_error = base64_error or self.default_base64_error
        self.length_error = length_error or self.default_length_error
        self.max_size = max_size

    def __call__(self, value):
        data = value.split(";base64,")[-1].encode("utf-8")
        try:
            data = base64.b64decode(data)
        except binascii.Error:
            raise ValidationError(self.base64_error)
        if self.max_size:
            if len(data) > self.max_size:
                raise ValidationError(self.length_error)
        return value


class ContainsLetterValidator(RegexValidator):
    regex = r"[^\W\d_]+"
    message = "Upewnij się, że ta wartość zawiera przynajmniej jedną literę."

    def __call__(self, value):
        return super().__call__(strip_tags(value))


def validate_uploaded_file(file: File, allowed_extensions_mime_types: Dict[str, FrozenSet[str]], max_file_size: int):

    # check file size
    if file.size > max_file_size:
        logger.exception("File %s - too big, max size is %s bytes.", file.name, max_file_size)
        raise DjangoValidationError(
            _("File too big, max size is %(max_file_size)s bytes."), params={"max_file_size": max_file_size}
        )

    if not file.name or not file.name.strip():
        logger.exception("Uploaded file has no name.")
        raise DjangoValidationError(_("Uploaded file has no name."))

    # check file extension
    ext = Path(file.name).suffix.lstrip(".").lower()
    if not ext:
        logger.exception("File %s - no file extension.", file.name)
        raise DjangoValidationError(_("File %(name)s has no extension."), params={"name": file.name})
    if ext not in allowed_extensions_mime_types:
        logger.exception("File %s - invalid file extension: %s.", file.name, ext)
        raise DjangoValidationError(_("Invalid file extension: %(ext)s."), params={"ext": ext})

    # magic mimetype vs file extension
    file.seek(0)
    mime_type = magic.from_buffer(file.read(), mime=True)
    file.seek(0)

    if mime_type not in allowed_extensions_mime_types[ext]:
        logger.exception("File %s - MIME type: %s does not match file extension: %s.", file.name, mime_type, ext)
        raise DjangoValidationError(_("Invalid file format"))
