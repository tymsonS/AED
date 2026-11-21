import json
from contextlib import nullcontext
from typing import ContextManager, List, Optional, Tuple
from unittest.mock import patch

import falcon
import pytest
from django.conf import settings
from falcon import HTTP_201, HTTP_422, testing
from werkzeug.utils import secure_filename

from mcod.submissions.attachments import AttachmentDTO
from mcod.submissions.models import SubmissionEvent
from mcod.submissions.views import GenericSubmissionView

_ENDPOINT = "/submissions/generic"
_BOUNDARY = "TestBoundaryMCOD001"
_JSONAPI_CONTENT_TYPE = "application/vnd.api+json"


def _json_body(subject: str, content: str = "Test content for the form.", **extra) -> dict:
    attrs: dict = {"subject": subject, "content": content, **extra}
    return {"data": {"type": "generic-contact-submission", "attributes": attrs}}


def _make_multipart_body(
    boundary: str,
    data_json: str,
    files: Optional[List[Tuple[str, bytes]]] = None,
) -> bytes:
    """Build a ``multipart/form-data`` body from a JSON data part and optional file parts."""
    _MIME = {
        "png": "image/png",
        "jpg": "image/jpeg",
        "pdf": "application/pdf",
        "doc": "application/msword",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xls": "application/vnd.ms-excel",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "csv": "text/csv",
        "xml": "application/xml",
        "zip": "application/zip",
        "exe": "application/octet-stream",
    }

    body = b""
    body += f"--{boundary}\r\n".encode()
    body += b'Content-Disposition: form-data; name="data"\r\n\r\n'
    body += data_json.encode()
    body += b"\r\n"

    for filename, content_bytes in files or []:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
        mime = _MIME.get(ext, "application/octet-stream")
        body += f"--{boundary}\r\n".encode()
        body += f'Content-Disposition: form-data; name="attachments"; filename="{filename}"\r\n'.encode()
        body += f"Content-Type: {mime}\r\n\r\n".encode()
        body += content_bytes
        body += b"\r\n"

    body += f"--{boundary}--\r\n".encode()
    return body


def _multipart_headers(boundary: str) -> dict:
    return {"Content-Type": f"multipart/form-data; boundary={boundary}"}


def _get_pointers(resp_json: dict) -> List[str]:
    return [err.get("source", {}).get("pointer", "") for err in resp_json.get("errors", [])]


def _get_codes(resp_json: dict) -> List[str]:
    return [err.get("code", "") for err in resp_json.get("errors", [])]


def _get_details(resp_json: dict) -> List[str]:
    return [err.get("detail", "") for err in resp_json.get("errors", [])]


_HAPPY_PATH_PARAMS = [
    pytest.param("DATA", "SHARING", id="data_sharing"),
    pytest.param("DATA", "STANDARDS", id="data_standards"),
    pytest.param("DATA", "HVD", id="data_hvd"),
    pytest.param("DATA", "DGA", id="data_dga"),
    pytest.param("DATA", "OTHER", id="data_other"),
    pytest.param("PORTAL", "FEATURES", id="portal_features"),
    pytest.param("PORTAL", "PROFILES", id="portal_profiles"),
    pytest.param("PORTAL", "PERMISSIONS", id="portal_permissions"),
    pytest.param("PORTAL", "BUGS", id="portal_bugs"),
    pytest.param("PORTAL", "OTHER", id="portal_other"),
    pytest.param("DATA_PROTECTION", None, id="data_protection_no_category"),
    pytest.param("LEGAL", None, id="legal_no_category"),
    pytest.param("OTHER", None, id="other_no_category"),
]


@pytest.mark.parametrize("subject, category", _HAPPY_PATH_PARAMS)
def test_happy_path_returns_201(client14: testing.TestClient, subject: str, category: Optional[str]) -> None:
    initial_count = SubmissionEvent.objects.count()
    attrs: dict = {"content": "This is a test message for the generic form."}
    if category is not None:
        attrs["category"] = category
    payload = {"data": {"type": "generic-contact-submission", "attributes": {**{"subject": subject}, **attrs}}}

    resp = client14.simulate_post(
        _ENDPOINT,
        json=payload,
        headers={"Content-Type": _JSONAPI_CONTENT_TYPE},
    )

    assert resp.status == HTTP_201, resp.json
    assert resp.json["data"]["type"] == "generic-contact-submission"
    assert resp.json["data"]["attributes"]["message"]
    assert SubmissionEvent.objects.count() == initial_count + 1


_FORBIDDEN_COMBO_PARAMS = [
    pytest.param("DATA", "SUGGEST_DATA", id="data_suggest_data"),
    pytest.param("DATA", "SUGGEST_REUSE", id="data_suggest_reuse"),
    pytest.param("DATA", "FEEDBACK", id="data_feedback"),
    pytest.param("LEGAL", "OTHER", id="legal_with_category"),
    pytest.param("DATA_PROTECTION", "OTHER", id="data_protection_with_category"),
    pytest.param("OTHER", "OTHER", id="other_with_category"),
]


@pytest.mark.parametrize("subject, category", _FORBIDDEN_COMBO_PARAMS)
def test_forbidden_combo_returns_422(client14: testing.TestClient, subject: str, category: str) -> None:
    initial_count = SubmissionEvent.objects.count()
    payload = _json_body(subject, category=category)

    resp = client14.simulate_post(
        _ENDPOINT,
        json=payload,
        headers={"Content-Type": _JSONAPI_CONTENT_TYPE},
    )

    assert resp.status == HTTP_422, resp.json
    assert _get_pointers(resp.json) == ["/data/attributes/category"]
    assert _get_codes(resp.json) == ["validation_error"]
    assert SubmissionEvent.objects.count() == initial_count


_MISSING_CATEGORY_PARAMS = [
    pytest.param("DATA", id="data_no_category"),
    pytest.param("PORTAL", id="portal_no_category"),
]


@pytest.mark.parametrize("subject", _MISSING_CATEGORY_PARAMS)
def test_missing_required_category_returns_422(client14: testing.TestClient, subject: str) -> None:
    initial_count = SubmissionEvent.objects.count()
    payload = _json_body(subject)

    resp = client14.simulate_post(
        _ENDPOINT,
        json=payload,
        headers={"Content-Type": _JSONAPI_CONTENT_TYPE},
    )

    assert resp.status == HTTP_422, resp.json
    assert _get_pointers(resp.json) == ["/data/attributes/category"]
    assert _get_codes(resp.json) == ["validation_error"]
    assert SubmissionEvent.objects.count() == initial_count


_CONTENT_VALIDATION_PARAMS = [
    pytest.param("", "content_empty", id="content_empty"),
    pytest.param("x" * 3001, "content_exceeding_3000", id="content_exceeding_3000"),
]


@pytest.mark.parametrize("content,pointer_field", _CONTENT_VALIDATION_PARAMS)
def test_invalid_content_returns_422(client14: testing.TestClient, content: str, pointer_field: str) -> None:
    initial_count = SubmissionEvent.objects.count()
    payload = _json_body("DATA_PROTECTION", content=content)

    resp = client14.simulate_post(
        _ENDPOINT,
        json=payload,
        headers={"Content-Type": _JSONAPI_CONTENT_TYPE},
    )

    assert resp.status == HTTP_422, resp.json
    assert _get_pointers(resp.json) == ["/data/attributes/content"]
    assert _get_codes(resp.json) == ["validation_error"]
    assert SubmissionEvent.objects.count() == initial_count


_EMAIL_VALIDATION_PARAMS = [
    pytest.param("invalidemail.com", "email_missing_at", id="email_without_at"),
    pytest.param("user@", "email_missing_domain", id="email_without_domain"),
]


@pytest.mark.parametrize("email,case", _EMAIL_VALIDATION_PARAMS)
def test_invalid_email_returns_422(client14: testing.TestClient, email: str, case: str) -> None:
    initial_count = SubmissionEvent.objects.count()
    payload = _json_body("DATA_PROTECTION", applicant_email=email)

    resp = client14.simulate_post(
        _ENDPOINT,
        json=payload,
        headers={"Content-Type": _JSONAPI_CONTENT_TYPE},
    )

    assert resp.status == HTTP_422, resp.json
    assert _get_pointers(resp.json) == ["/data/attributes/applicant_email"]
    assert _get_codes(resp.json) == ["validation_error"]
    assert SubmissionEvent.objects.count() == initial_count


def test_applicant_full_name_exceeding_300_chars_returns_422(
    client14: testing.TestClient,
) -> None:
    initial_count = SubmissionEvent.objects.count()
    payload = _json_body("DATA_PROTECTION", applicant_full_name="A" * 301)

    resp = client14.simulate_post(
        _ENDPOINT,
        json=payload,
        headers={"Content-Type": _JSONAPI_CONTENT_TYPE},
    )

    assert resp.status == HTTP_422, resp.json
    assert _get_pointers(resp.json) == ["/data/attributes/applicant_full_name"]
    assert _get_codes(resp.json) == ["validation_error"]
    assert SubmissionEvent.objects.count() == initial_count


_ALLOWED_FILE_COUNTS = [1, 2, 3]


def test_plain_text_csv_attachment_returns_201(client14: testing.TestClient) -> None:
    # GIVEN
    initial_count = SubmissionEvent.objects.count()
    data_json = json.dumps(_json_body("DATA_PROTECTION", content="CSV attachment test."))
    body = _make_multipart_body(_BOUNDARY, data_json, [("report.csv", b"name,email\nJan,jan@example.com\n")])

    # WHEN
    resp = client14.simulate_post(
        _ENDPOINT,
        body=body,
        headers=_multipart_headers(_BOUNDARY),
    )

    # THEN
    assert resp.status == HTTP_201, resp.json
    assert SubmissionEvent.objects.count() == initial_count + 1


@pytest.mark.parametrize("file_count", _ALLOWED_FILE_COUNTS)
def test_allowed_file_count_returns_201(client14: testing.TestClient, file_count: int, valid_pdf_bytes: bytes) -> None:
    initial_count = SubmissionEvent.objects.count()
    data_json = json.dumps(_json_body("DATA_PROTECTION", content="Attachment test."))
    files = [(f"doc{i}.pdf", valid_pdf_bytes) for i in range(1, file_count + 1)]
    body = _make_multipart_body(_BOUNDARY, data_json, files)

    resp = client14.simulate_post(
        _ENDPOINT,
        body=body,
        headers=_multipart_headers(_BOUNDARY),
    )

    assert resp.status == HTTP_201, resp.json
    assert SubmissionEvent.objects.count() == initial_count + 1


_TOO_MANY_FILES_PARAMS = [
    pytest.param("en", "Maximum 3 files allowed per request. Got 3.", id="count_exceeded_en"),
    pytest.param("pl", "Maksymalna liczba plików na żądanie wynosi 3. Przesłano 3.", id="count_exceeded_pl"),
]


@pytest.mark.parametrize("lang,expected_detail", _TOO_MANY_FILES_PARAMS)
def test_too_many_files_returns_422(
    client14: testing.TestClient, valid_pdf_bytes: bytes, lang: str, expected_detail: str
) -> None:
    initial_count = SubmissionEvent.objects.count()
    data_json = json.dumps(_json_body("DATA_PROTECTION", content="Attachment test."))
    files = [(f"doc{i}.pdf", valid_pdf_bytes) for i in range(1, settings.GENERIC_SUBMISSION_MAX_ATTACHMENT_COUNT + 2)]
    body = _make_multipart_body(_BOUNDARY, data_json, files)

    resp = client14.simulate_post(
        f"{_ENDPOINT}?lang={lang}",
        body=body,
        headers=_multipart_headers(_BOUNDARY),
    )

    assert resp.status == HTTP_422, resp.json
    assert _get_pointers(resp.json) == ["/data/attributes/attachments"]
    assert _get_codes(resp.json) == ["attachment_count_exceeded"]
    assert _get_details(resp.json) == [expected_detail]
    assert SubmissionEvent.objects.count() == initial_count


_SIZE_EXCEEDED_PARAMS = [
    pytest.param("en", "Combined file size must not exceed 30 MB.", id="size_exceeded_en"),
    pytest.param("pl", "Łączny rozmiar pliku nie może przekraczać 30 MB.", id="size_exceeded_pl"),
]


@pytest.mark.parametrize("lang,expected_detail", _SIZE_EXCEEDED_PARAMS)
def test_combined_size_exceeded_returns_422(client14: testing.TestClient, lang: str, expected_detail: str) -> None:
    initial_count = SubmissionEvent.objects.count()
    data_json = json.dumps(_json_body("DATA_PROTECTION", content="Size limit test."))
    # Prefix with PDF magic bytes so libmagic validates successfully before the size limit is hit.
    large = b"%PDF-1.4\n" + bytes(15_100_000 - 9)  # 15.1 MB each → 30.2 MB combined
    files = [("big1.pdf", large), ("big2.pdf", large)]
    body = _make_multipart_body(_BOUNDARY, data_json, files)

    resp = client14.simulate_post(
        f"{_ENDPOINT}?lang={lang}",
        body=body,
        headers=_multipart_headers(_BOUNDARY),
    )

    assert resp.status == HTTP_422, resp.json
    assert _get_pointers(resp.json) == ["/data/attributes/attachments"]
    assert _get_codes(resp.json) == ["attachment_size_exceeded"]
    assert _get_details(resp.json) == [expected_detail]
    assert SubmissionEvent.objects.count() == initial_count


_MIME_MISMATCH_PARAMS = [
    pytest.param("en", "File content type 'image/jpeg' is not allowed for '.pdf' files.", id="mime_mismatch_en"),
    pytest.param("pl", "Typ zawartości pliku 'image/jpeg' jest niedozwolony dla plików '.pdf'.", id="mime_mismatch_pl"),
]


@pytest.mark.parametrize("lang,expected_detail", _MIME_MISMATCH_PARAMS)
def test_mime_type_mismatch_returns_422(
    client14: testing.TestClient, valid_jpeg_bytes: bytes, lang: str, expected_detail: str
) -> None:
    initial_count = SubmissionEvent.objects.count()
    data_json = json.dumps(_json_body("DATA_PROTECTION", content="MIME mismatch test."))
    files = [("document.pdf", valid_jpeg_bytes)]
    body = _make_multipart_body(_BOUNDARY, data_json, files)

    resp = client14.simulate_post(
        f"{_ENDPOINT}?lang={lang}",
        body=body,
        headers=_multipart_headers(_BOUNDARY),
    )

    assert resp.status == HTTP_422, resp.json
    assert _get_pointers(resp.json) == ["/data/attributes/attachments"]
    assert _get_codes(resp.json) == ["invalid_attachment_mime_type"]
    assert _get_details(resp.json) == [expected_detail]
    assert SubmissionEvent.objects.count() == initial_count


def test_path_traversal_filename_is_sanitized_and_succeeds(client14: testing.TestClient, valid_pdf_bytes: bytes) -> None:
    """Path-traversal components are stripped from the filename before processing."""
    initial_count = SubmissionEvent.objects.count()
    data_json = json.dumps(_json_body("DATA_PROTECTION", content="Path traversal test."))
    files = [("../../../etc/safe.pdf", valid_pdf_bytes)]
    body = _make_multipart_body(_BOUNDARY, data_json, files)

    with patch("mcod.submissions.views.secure_filename", wraps=secure_filename) as mock_secure:
        resp = client14.simulate_post(
            _ENDPOINT,
            body=body,
            headers=_multipart_headers(_BOUNDARY),
        )

    assert resp.status == HTTP_201, resp.json
    assert SubmissionEvent.objects.count() == initial_count + 1
    mock_secure.assert_called_once_with("../../../etc/safe.pdf")


_INVALID_ATTACHMENT_PARAMS = [
    pytest.param(
        "../../../../evil",
        None,
        "invalid_attachment_extension",
        id="malicious_filename_without_extension",
    ),
    pytest.param(
        "document.pdf",
        ("_is_allowed_extension", False),
        "invalid_attachment_extension",
        id="disallowed_extension",
    ),
    pytest.param(
        "document.pdf",
        ("_is_allowed_mime_type", False),
        "invalid_attachment_mime_type",
        id="disallowed_mime_type",
    ),
]


@pytest.mark.parametrize("filename,patch_spec,expected_code", _INVALID_ATTACHMENT_PARAMS)
def test_invalid_attachment_returns_422(
    client14: testing.TestClient,
    valid_pdf_bytes: bytes,
    filename: str,
    patch_spec: Optional[Tuple[str, bool]],
    expected_code: str,
) -> None:
    # GIVEN
    initial_count = SubmissionEvent.objects.count()
    data_json = json.dumps(_json_body("DATA_PROTECTION", content="Attachment validation test."))
    body = _make_multipart_body(_BOUNDARY, data_json, [(filename, valid_pdf_bytes)])
    if patch_spec:
        attr, return_value = patch_spec
        ctx: ContextManager = patch.object(GenericSubmissionView.POST, attr, return_value=return_value)
    else:
        ctx = nullcontext()

    # WHEN
    with ctx:
        resp = client14.simulate_post(_ENDPOINT, body=body, headers=_multipart_headers(_BOUNDARY))

    # THEN
    assert resp.status == HTTP_422, resp.json
    assert _get_pointers(resp.json) == ["/data/attributes/attachments"]
    assert _get_codes(resp.json) == [expected_code]
    assert SubmissionEvent.objects.count() == initial_count


_MISSING_DATA_PART_PARAMS = [
    pytest.param("en", "Missing 'data' part in multipart request.", id="missing_data_part_en"),
    pytest.param("pl", "Brakuje części 'data' w żądaniu multipart.", id="missing_data_part_pl"),
]


@pytest.mark.parametrize("lang,expected_detail", _MISSING_DATA_PART_PARAMS)
def test_missing_data_part_returns_400(
    client14: testing.TestClient, valid_pdf_bytes: bytes, lang: str, expected_detail: str
) -> None:
    initial_count = SubmissionEvent.objects.count()

    body = b""
    body += f"--{_BOUNDARY}\r\n".encode()
    body += b'Content-Disposition: form-data; name="attachments"; filename="doc1.pdf"\r\n'
    body += b"Content-Type: application/pdf\r\n\r\n"
    body += valid_pdf_bytes
    body += b"\r\n"
    body += f"--{_BOUNDARY}--\r\n".encode()

    resp = client14.simulate_post(
        f"{_ENDPOINT}?lang={lang}",
        body=body,
        headers=_multipart_headers(_BOUNDARY),
    )

    assert resp.status == falcon.HTTP_400, resp.json
    assert _get_codes(resp.json) == ["missing_data_part"]
    assert _get_details(resp.json) == [expected_detail]
    assert SubmissionEvent.objects.count() == initial_count


_INVALID_JSON_PARAMS = [
    pytest.param("en", "Invalid JSON in 'data' part.", id="invalid_json_en"),
    pytest.param("pl", "Nieprawidłowy JSON w części 'data'.", id="invalid_json_pl"),
]


@pytest.mark.parametrize("lang,expected_detail", _INVALID_JSON_PARAMS)
def test_invalid_json_in_data_part_returns_400(client14: testing.TestClient, lang: str, expected_detail: str) -> None:
    initial_count = SubmissionEvent.objects.count()
    body = _make_multipart_body(_BOUNDARY, "{ invalid json text }", [])

    resp = client14.simulate_post(
        f"{_ENDPOINT}?lang={lang}",
        body=body,
        headers=_multipart_headers(_BOUNDARY),
    )

    assert resp.status == falcon.HTTP_400, resp.json
    assert _get_codes(resp.json) == ["invalid_json"]
    assert _get_details(resp.json) == [expected_detail]
    assert SubmissionEvent.objects.count() == initial_count


def test_service_failure_returns_500(client14: testing.TestClient) -> None:
    with patch("mcod.submissions.views.create_submission_event", return_value=None):
        payload = _json_body("DATA_PROTECTION")

        resp = client14.simulate_post(
            _ENDPOINT,
            json=payload,
            headers={"Content-Type": _JSONAPI_CONTENT_TYPE},
        )

    assert resp.status == falcon.HTTP_500


_LOCALIZATION_PARAMS = [
    pytest.param("pl", "Twoje zgłoszenie zostało przyjęte.", id="polish"),
    pytest.param("en", "Your submission has been received.", id="english"),
]


@pytest.mark.parametrize("lang,expected_message", _LOCALIZATION_PARAMS)
def test_lang_returns_localized_message(client14: testing.TestClient, lang: str, expected_message: str) -> None:
    payload = _json_body("DATA_PROTECTION")

    resp = client14.simulate_post(
        f"{_ENDPOINT}?lang={lang}",
        json=payload,
        headers={"Content-Type": _JSONAPI_CONTENT_TYPE},
    )

    assert resp.status == HTTP_201, resp.json
    assert resp.json["data"]["attributes"]["message"] == expected_message


@patch("mcod.submissions.views.send_generic_submission_email_task")
def test_task_dispatched_with_correct_args(
    mock_task,
    client14: testing.TestClient,
) -> None:
    payload = _json_body(
        "DATA",
        category="SHARING",
        applicant_full_name="Jan Kowalski",
        applicant_email="jan@example.com",
    )

    resp = client14.simulate_post(
        _ENDPOINT,
        json=payload,
        headers={"Content-Type": _JSONAPI_CONTENT_TYPE},
    )

    assert resp.status == HTTP_201
    mock_task.delay.assert_called_once()
    call_kwargs = mock_task.delay.call_args[1]
    assert call_kwargs["event_id"] == int(resp.json["data"]["id"])
    assert call_kwargs["content"] == "Test content for the form."
    assert call_kwargs["applicant_full_name"] == "Jan Kowalski"
    assert call_kwargs["applicant_email"] == "jan@example.com"
    assert "attachments" not in call_kwargs


@pytest.mark.parametrize(
    "file_count",
    [
        pytest.param(1, id="one_attachment"),
        pytest.param(3, id="three_attachments"),
    ],
)
@patch("mcod.submissions.views.send_generic_submission_email_task")
@patch("mcod.submissions.views.AttachmentStagingManager.stage")
def test_task_dispatched_with_attachments(
    mock_stage,
    mock_task,
    client14: testing.TestClient,
    valid_pdf_bytes: bytes,
    file_count: int,
) -> None:
    files = [(f"doc_{i}.pdf", valid_pdf_bytes) for i in range(file_count)]
    data_json = json.dumps(_json_body("DATA_PROTECTION", content="With file."))
    body = _make_multipart_body(_BOUNDARY, data_json, files)

    resp = client14.simulate_post(
        _ENDPOINT,
        body=body,
        headers=_multipart_headers(_BOUNDARY),
    )

    assert resp.status == HTTP_201
    event_id = int(resp.json["data"]["id"])
    expected_dtos = [AttachmentDTO(filename=name, content=valid_pdf_bytes, mime_type="application/pdf") for name, _ in files]
    mock_stage.assert_called_once_with(event_id, expected_dtos)
    mock_task.delay.assert_called_once()
    call_kwargs = mock_task.delay.call_args[1]
    assert "attachments" not in call_kwargs
