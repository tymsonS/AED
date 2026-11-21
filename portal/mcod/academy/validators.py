from django.conf import settings
from django.utils.deconstruct import deconstructible

from mcod.academy.constants import ALLOWED_COURSE_FILE_EXTENSIONS_MIME_TYPES
from mcod.lib.field_validators import validate_uploaded_file


@deconstructible
class CourseFileValidator:
    def __call__(self, file):

        validate_uploaded_file(
            file,
            allowed_extensions_mime_types=ALLOWED_COURSE_FILE_EXTENSIONS_MIME_TYPES,
            max_file_size=settings.IMAGE_UPLOAD_MAX_SIZE,
        )

    def __eq__(self, other):
        return isinstance(other, self.__class__)

    def deconstruct(self):
        return f"{self.__class__.__module__}.{self.__class__.__qualname__}", [], {}
