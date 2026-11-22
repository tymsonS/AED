import json
import logging
from collections import namedtuple
from functools import partial
from typing import List, Optional, Tuple

import falcon
import magic
import sentry_sdk
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from falcon.media.multipart import BodyPart
from marshmallow import ValidationError as MarshmallowValidationError
from webargs.falconparser import HTTPError
from werkzeug.utils import secure_filename

from mcod.core.api.handlers import CreateOneHdlr
from mcod.core.api.hooks import login_optional
from mcod.core.api.views import JsonAPIView
from mcod.core.versioning import versioned
from mcod.submissions.attachments import AttachmentDTO, AttachmentStagingManager
from mcod.submissions.deserializers import CreateGenericSubmissionRequest
from mcod.submissions.exceptions import (
    AttachmentCountExceededError,
    AttachmentSizeExceededError,
    InvalidAttachmentExtensionError,
    InvalidAttachmentMimeTypeError,
    InvalidJsonError,
    MissingDataPartError,
    ValidationError,
)
from mcod.submissions.models import Category, Subject, SubmissionEvent
from mcod.submissions.serializers import GenericSubmissionApiResponse
from mcod.submissions.service import create_submission_event
from mcod.submissions.tasks import send_generic_submission_email_task

logger = logging.getLogger(__name__)

_GenericSubmissionResult = namedtuple("GenericSubmissionResult", ["id", "message"])


class GenericSubmissionView(JsonAPIView):
    @falcon.before(login_optional)
    @versioned
    def on_post(self, request, response, *args, **kwargs):
        self.handle_post(request, response, self.POST, *args, **kwargs)

    class POST(CreateOneHdlr):
        deserializer_schema = CreateGenericSubmissionRequest
        serializer_schema = partial(GenericSubmissionApiResponse, many=False)

        @staticmethod
        def _is_allowed_extension(ext: str) -> bool:
            return ext in settings.GENERIC_SUBMISSION_ALLOWED_EXTENSION_MIME_TYPES

        @staticmethod
        def _is_allowed_mime_type(ext: str, mime_type: str) -> bool:
            allowed = settings.EXTENSION_TO_MIME_TYPE_MAP.get(ext, frozenset())
            return mime_type in allowed

        def clean(self, *args, **kwargs) -> dict:
            content_type = self.request.content_type or ""
            if "multipart/form-data" in content_type:
                return self._clean_multipart()
            try:
                return super().clean(*args, **kwargs)
            except HTTPError as exc:
                raise ValidationError(errors=getattr(exc, "errors", {})) from exc

        def _clean_multipart(self) -> dict:
            form = self.request.get_media()
            data_text = None
            attachment_files: List[Tuple[str, bytes, str]] = []
            attachments_total_size = 0
            for part in form:
                if part.name == "data":
                    data_text = part.text
                elif part.name == "attachments":
                    filename, file_bytes, mime_type, attachments_total_size = self._process_attachment(
                        part, attachment_files, attachments_total_size
                    )
                    attachment_files.append((filename, file_bytes, mime_type))

            cleaned = self._parse_and_validate_data(data_text)
            cleaned["_attachments"] = attachment_files
            return cleaned

        def _process_attachment(
            self, part: BodyPart, attachment_files: List[Tuple[str, bytes, str]], total_size: int
        ) -> Tuple[str, bytes, str, int]:
            if len(attachment_files) >= settings.GENERIC_SUBMISSION_MAX_ATTACHMENT_COUNT:
                raise AttachmentCountExceededError(
                    count=settings.GENERIC_SUBMISSION_MAX_ATTACHMENT_COUNT,
                    actual=len(attachment_files),
                )

            filename: str = secure_filename(part.filename)
            ext: str = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            if not self._is_allowed_extension(ext):
                raise InvalidAttachmentExtensionError(ext=ext)

            file_bytes, mime_type, total_size = self._read_file_chunks(part, ext, total_size)
            return filename, file_bytes, mime_type, total_size

        def _read_file_chunks(self, part: BodyPart, ext: str, total_size: int) -> Tuple[bytes, str, int]:
            file_data = bytearray()
            while True:
                chunk = part.stream.read(8192)
                if not chunk:
                    break

                file_data.extend(chunk)
                total_size += len(chunk)

                if total_size > settings.GENERIC_SUBMISSION_MAX_TOTAL_ATTACHMENT_SIZE_BYTES:
                    raise AttachmentSizeExceededError()

            full_file_bytes = bytes(file_data)
            # Validate after full load so libmagic can read the ZIP Central Directory (needed for .docx/.xlsx).
            mime_type = magic.from_buffer(full_file_bytes, mime=True)
            if not self._is_allowed_mime_type(ext, mime_type):
                raise InvalidAttachmentMimeTypeError(mime=mime_type, ext=ext)

            return full_file_bytes, mime_type, total_size

        def _parse_and_validate_data(self, data_text: Optional[str]) -> dict:
            if data_text is None:
                raise MissingDataPartError()

            try:
                json_data = json.loads(data_text)
            except json.JSONDecodeError:
                raise InvalidJsonError()

            schema = self.deserializer_schema(context={"request": self.request})
            try:
                return schema.load(json_data)
            except MarshmallowValidationError as exc:
                raise ValidationError(errors=exc.messages)

        def _get_data(self, cleaned: dict, *args, **kwargs) -> _GenericSubmissionResult:
            attrs = cleaned["data"]["attributes"]
            subject = Subject(attrs["subject"])
            category_val = attrs.get("category")
            category = Category(category_val) if category_val else None

            event: Optional[SubmissionEvent] = create_submission_event(
                subject=subject,
                category=category,
                submission_date=timezone.now(),
            )
            if event is None:
                raise falcon.HTTPInternalServerError()

            attachment_files: List[Tuple[str, bytes, str]] = cleaned.get("_attachments", [])
            attachments = [AttachmentDTO(filename=name, content=data, mime_type=mime) for name, data, mime in attachment_files]
            staging = AttachmentStagingManager()
            try:
                staging.stage(event.pk, attachments)
            except Exception as exc:
                logger.error(f"Failed to stage attachments for event {event.pk}: {exc}")
                sentry_sdk.capture_exception(exc)
                raise falcon.HTTPInternalServerError()

            send_generic_submission_email_task.delay(
                event_id=event.pk,
                content=attrs.get("content", ""),
                applicant_full_name=attrs.get("applicant_full_name"),
                applicant_email=attrs.get("applicant_email"),
            )
            logger.info(f"Dispatched send_generic_submission_email_task for event_id={event.pk}")

            return _GenericSubmissionResult(
                id=str(event.pk),
                message=str(_("Your submission has been received.")),
            )
