import falcon
from django.utils.translation import gettext_lazy as _
from webargs.falconparser import HTTPError


class ValidationError(HTTPError):
    def __init__(self, errors: dict) -> None:
        super().__init__(falcon.HTTP_422, errors=errors, code="validation_error")


class MissingDataPartError(HTTPError):
    def __init__(self) -> None:
        super().__init__(
            falcon.HTTP_400, errors={"data": _("Missing 'data' part in multipart request.")}, code="missing_data_part"
        )


class InvalidJsonError(HTTPError):
    def __init__(self) -> None:
        super().__init__(falcon.HTTP_400, errors={"data": _("Invalid JSON in 'data' part.")}, code="invalid_json")


class AttachmentCountExceededError(HTTPError):
    def __init__(self, count: int, actual: int) -> None:
        super().__init__(
            falcon.HTTP_422,
            errors={
                "data": {
                    "attributes": {
                        "attachments": [
                            _("Maximum {count} files allowed per request. Got {actual}.").format(count=count, actual=actual)
                        ]
                    }
                }
            },
            code="attachment_count_exceeded",
        )


class InvalidAttachmentExtensionError(HTTPError):
    def __init__(self, ext: str) -> None:
        super().__init__(
            falcon.HTTP_422,
            errors={"data": {"attributes": {"attachments": [_("File extension '.{ext}' is not allowed.").format(ext=ext)]}}},
            code="invalid_attachment_extension",
        )


class InvalidAttachmentMimeTypeError(HTTPError):
    def __init__(self, mime: str, ext: str) -> None:
        super().__init__(
            falcon.HTTP_422,
            errors={
                "data": {
                    "attributes": {
                        "attachments": [
                            _("File content type '{mime}' is not allowed for '.{ext}' files.").format(mime=mime, ext=ext)
                        ]
                    }
                }
            },
            code="invalid_attachment_mime_type",
        )


class AttachmentSizeExceededError(HTTPError):
    def __init__(self) -> None:
        super().__init__(
            falcon.HTTP_422,
            errors={"data": {"attributes": {"attachments": [_("Combined file size must not exceed 30 MB.")]}}},
            code="attachment_size_exceeded",
        )
