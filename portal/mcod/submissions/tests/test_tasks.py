import csv
import json
from datetime import timedelta
from pathlib import Path
from typing import List

import pytest
from django.core.mail import EmailMessage
from django.test import override_settings
from django.utils import timezone

from mcod.submissions.attachments import AttachmentDTO, AttachmentStagingManager
from mcod.submissions.factories import SubmissionEventFactory
from mcod.submissions.models import Category, Subject, SubmissionEvent
from mcod.submissions.tasks import (
    generate_statistical_report_for_all_submissions_task,
    generate_submission_unit_report_task,
    send_generic_submission_email_task,
)


@pytest.fixture
def submission_event() -> SubmissionEvent:
    return SubmissionEvent.objects.create(
        subject=Subject.DATA.value,
        category=Category.SHARING.value,
        submission_date=timezone.datetime(2026, 8, 15, 10, 30, tzinfo=timezone.utc),
    )


class TestSendGenericSubmissionEmailTask:
    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", DEBUG=False)
    def test_sends_email_with_all_fields(self, submission_event: SubmissionEvent, mailoutbox: List[EmailMessage]) -> None:
        result = send_generic_submission_email_task(
            event_id=submission_event.pk,
            content="Treść wiadomości testowej",
            applicant_full_name="Jan Kowalski",
            applicant_email="jan@example.com",
        )

        assert result == {"sent": True, "event_id": submission_event.pk}
        assert len(mailoutbox) == 1
        msg: EmailMessage = mailoutbox[0]
        assert msg.subject == f"Udostępnianie danych w portalu | ID: {submission_event.pk}"
        assert msg.to == ["kontakt@dane.gov.pl"]
        assert msg.from_email == "no-reply@dane.gov.pl"

        # Plain-text body contains all expected labels and values
        assert "ID Zgłoszenia:" in msg.body
        assert str(submission_event.pk) in msg.body
        assert "Data zgłoszenia:" in msg.body
        assert "2026-08-15 12:30" in msg.body
        assert "Temat:" in msg.body
        assert "Dane" in msg.body
        assert "Kategoria:" in msg.body
        assert "Udostępnianie danych w portalu" in msg.body
        assert "Imię i nazwisko zgłaszającego:" in msg.body
        assert "Jan Kowalski" in msg.body
        assert "Adres e-mail zgłaszającego:" in msg.body
        assert "jan@example.com" in msg.body
        assert "Treść korespondencji:" in msg.body
        assert "Treść wiadomości testowej" in msg.body

        # HTML alternative present with same field values
        assert len(msg.alternatives) == 1
        html_content, content_type = msg.alternatives[0]
        assert content_type == "text/html"
        assert "Jan Kowalski" in html_content
        assert "jan@example.com" in html_content
        assert "Treść wiadomości testowej" in html_content
        assert "Dane" in html_content
        assert "Udostępnianie danych w portalu" in html_content

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", DEBUG=False)
    def test_optional_fields_show_dash_when_absent(self, mailoutbox: List[EmailMessage]) -> None:
        event = SubmissionEvent.objects.create(
            subject=Subject.DATA_PROTECTION.value,
            category="",
            submission_date=timezone.datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
        )

        send_generic_submission_email_task(
            event_id=event.pk,
            content="Minimal submission",
            applicant_full_name=None,
            applicant_email=None,
        )

        msg: EmailMessage = mailoutbox[0]
        assert msg.subject == f"Ochrona danych osobowych w portalu | ID: {event.pk}"
        lines = msg.body.splitlines()
        cat_idx = next(i for i, line in enumerate(lines) if "Kategoria:" in line)
        assert lines[cat_idx + 1].strip() == "-"
        name_idx = next(i for i, line in enumerate(lines) if "Imię i nazwisko zgłaszającego:" in line)
        assert lines[name_idx + 1].strip() == "-"
        email_idx = next(i for i, line in enumerate(lines) if "Adres e-mail zgłaszającego:" in line)
        assert lines[email_idx + 1].strip() == "-"

    @pytest.mark.parametrize(
        "file_count",
        [
            pytest.param(1, id="one_attachment"),
            pytest.param(3, id="three_attachments"),
        ],
    )
    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", DEBUG=False)
    def test_sends_email_with_attachment(
        self, submission_event: SubmissionEvent, tmp_path: Path, file_count: int, mailoutbox: List[EmailMessage]
    ) -> None:
        file_content = b"fake pdf content for testing"
        attachments = [
            AttachmentDTO(filename=f"report_{i}.pdf", content=file_content, mime_type="application/pdf")
            for i in range(file_count)
        ]

        with override_settings(GENERIC_SUBMISSION_STAGING_ROOT=str(tmp_path)):
            staging = AttachmentStagingManager()
            staging.stage(submission_event.pk, attachments)

            send_generic_submission_email_task(
                event_id=submission_event.pk,
                content="Attachment test",
                applicant_full_name=None,
                applicant_email=None,
            )

        msg: EmailMessage = mailoutbox[0]
        assert msg.attachments == [(a.filename, a.content, a.mime_type) for a in attachments]


@pytest.mark.django_db
class TestGenerateSubmissionReportsTasks:

    @pytest.mark.parametrize(
        "filters, expected_count",
        [
            ({"subject": "", "category": "", "date_from": "", "date_to": ""}, 3),
            ({"subject": "DATA", "category": "", "date_from": "", "date_to": ""}, 2),
            ({"subject": "", "category": "BUGS", "date_from": "", "date_to": ""}, 1),
        ],
    )
    def test_unit_report_filters_and_serializes_events_correctly(self, admin, tmp_path, filters, expected_count):
        # GIVEN
        event_1 = SubmissionEventFactory.create(subject=Subject.DATA.value, category=Category.SHARING.value)
        event_2 = SubmissionEventFactory.create(subject=Subject.DATA.value, category=Category.HVD.value)
        event_3 = SubmissionEventFactory.create(subject=Subject.PORTAL.value, category=Category.BUGS.value)

        # WHEN
        with override_settings(REPORTS_MEDIA_ROOT=str(tmp_path)):
            result_json = generate_submission_unit_report_task(user_id=admin.pk, **filters)

        # THEN
        result = json.loads(result_json)
        file_path = tmp_path / "submissions" / Path(result["csv_file"]).name

        with open(file_path, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f, delimiter=";")
            rows = list(reader)

        assert len(rows) == expected_count + 1
        assert rows[0] == ["ID zgłoszenia", "ID referencyjne", "Link do zgłoszenia", "Temat", "Kategoria", "Data zgłoszenia"]

        # Deep assertion on all rows to ensure serialization accuracy and "-id" ordering
        if expected_count == 3:
            # Events are ordered by -id, so event_3 is first in the CSV (after header), then event_2, then event_1
            assert rows[1] == [
                str(event_3.id),
                "",
                "",
                "Portal dane.gov.pl",
                "Błędy w działaniu portalu",
                timezone.localtime(event_3.submission_date).strftime("%Y-%m-%d %H:%M:%S"),
            ]
            assert rows[2] == [
                str(event_2.id),
                "",
                "",
                "Dane",
                "Dane o wysokiej wartości (HVD)",
                timezone.localtime(event_2.submission_date).strftime("%Y-%m-%d %H:%M:%S"),
            ]
            assert rows[3] == [
                str(event_1.id),
                "",
                "",
                "Dane",
                "Udostępnianie danych w portalu",
                timezone.localtime(event_1.submission_date).strftime("%Y-%m-%d %H:%M:%S"),
            ]

    def test_stats_report_calculates_all_combinations_accurately(self, admin, tmp_path):
        # GIVEN
        SubmissionEventFactory.create_batch(3, subject=Subject.DATA.value, category=Category.SHARING.value)
        SubmissionEventFactory.create_batch(2, subject=Subject.PORTAL.value, category=Category.BUGS.value)
        SubmissionEventFactory.create(subject=Subject.DATA.value, category=Category.HVD.value)

        # WHEN
        with override_settings(REPORTS_MEDIA_ROOT=str(tmp_path)):
            result_json = generate_statistical_report_for_all_submissions_task(
                user_id=admin.pk,
                date_from="",
                date_to="",
            )

        # THEN
        result = json.loads(result_json)
        file_path = tmp_path / "submissions" / Path(result["csv_file"]).name

        with open(file_path, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f, delimiter=";")
            rows = list(reader)

        # Assert total number of rows is exactly 17 (1 header + 16 data rows)
        assert len(rows) == 17
        assert rows[0] == ["Temat", "Kategoria", "Liczba zgłoszeń"]

        # Convert CSV rows to a dictionary for exact assertions
        stats_map = {(r[0], r[1]): int(r[2]) for r in rows[1:]}

        # Explicitly define all 16 expected combinations mapped in the system
        expected_stats = {
            ("Dane", "Udostępnianie danych w portalu"): 3,
            ("Dane", "Zaproponuj dane do udostępnienia w portalu"): 0,
            ("Dane", "Zaproponuj przykład ponownego wykorzystania danych"): 0,
            ("Dane", "Zgłoś uwagi do danych udostępnionych w portalu"): 0,
            ("Dane", "Standardy otwartości danych"): 0,
            ("Dane", "Dane o wysokiej wartości (HVD)"): 1,
            ("Dane", "Chronione dane (DGA)"): 0,
            ("Dane", "Inne"): 0,
            ("Portal dane.gov.pl", "Funkcjonalności portalu"): 0,
            ("Portal dane.gov.pl", "Zakładanie profili dostawców"): 0,
            ("Portal dane.gov.pl", "Nadawanie uprawnień"): 0,
            ("Portal dane.gov.pl", "Błędy w działaniu portalu"): 2,
            ("Portal dane.gov.pl", "Inne"): 0,
            ("Ochrona danych osobowych w portalu", ""): 0,
            ("Regulacje prawne dotyczące otwartości danych", ""): 0,
            ("Inne", ""): 0,
        }

        # Verify that all combinations were aggregated correctly
        assert stats_map == expected_stats

    def test_stats_report_respects_date_filters_and_filename_conventions(self, admin, tmp_path):
        # GIVEN
        now = timezone.now()

        # Event inside the date range
        SubmissionEventFactory.create(subject=Subject.DATA.value, category=Category.SHARING.value, submission_date=now)
        # Event outside the date range
        SubmissionEventFactory.create(
            subject=Subject.DATA.value, category=Category.SHARING.value, submission_date=now - timedelta(days=10)
        )

        date_from_str = (now - timedelta(days=2)).date().isoformat()
        date_to_str = (now + timedelta(days=2)).date().isoformat()

        # WHEN
        with override_settings(REPORTS_MEDIA_ROOT=str(tmp_path)):
            result_json = generate_statistical_report_for_all_submissions_task(
                user_id=admin.pk,
                date_from=date_from_str,
                date_to=date_to_str,
            )

        # THEN
        result = json.loads(result_json)
        file_path = tmp_path / "submissions" / Path(result["csv_file"]).name

        with open(file_path, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f, delimiter=";")
            rows = list(reader)

        stats_map = {(r[0], r[1]): int(r[2]) for r in rows[1:]}

        # Only 1 event should be counted, despite 2 existing in the DB
        assert stats_map[("Dane", "Udostępnianie danych w portalu")] == 1
        assert sum(stats_map.values()) == 1

        # Validate strictly that filename is built correctly from both dates
        from_fmt = date_from_str.replace("-", "")
        to_fmt = date_to_str.replace("-", "")
        assert f"submissions_stats_from_{from_fmt}_to_{to_fmt}_" in result["csv_file"]
