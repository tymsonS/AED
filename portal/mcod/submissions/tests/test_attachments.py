from pathlib import Path

import pytest
from django.test import override_settings

from mcod.submissions.attachments import AttachmentDTO, AttachmentStagingManager


@pytest.mark.parametrize(
    "file_count",
    [
        pytest.param(0, id="no_attachments"),
        pytest.param(1, id="one_attachment"),
        pytest.param(3, id="three_attachments"),
    ],
)
def test_stage_and_load_round_trips_attachments(valid_pdf_bytes: bytes, tmp_path: Path, file_count: int) -> None:
    attachments = [
        AttachmentDTO(filename=f"doc_{i}.pdf", content=valid_pdf_bytes, mime_type="application/pdf") for i in range(file_count)
    ]

    with override_settings(GENERIC_SUBMISSION_STAGING_ROOT=str(tmp_path)):
        staging = AttachmentStagingManager()
        staging.stage(event_id=1, attachments=attachments)
        loaded = staging.load(event_id=1)

    assert loaded == attachments


def test_cleanup_removes_event_directory(valid_pdf_bytes: bytes, tmp_path: Path) -> None:
    attachment = AttachmentDTO(filename="report.pdf", content=valid_pdf_bytes, mime_type="application/pdf")

    with override_settings(GENERIC_SUBMISSION_STAGING_ROOT=str(tmp_path)):
        staging = AttachmentStagingManager()
        staging.stage(event_id=1, attachments=[attachment])
        event_dir = tmp_path / "1"
        assert event_dir.exists()

        staging.cleanup(event_id=1)

        assert not event_dir.exists()
        assert staging.load(event_id=1) == []
