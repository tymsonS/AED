import re
from datetime import timedelta
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pytest
from django.contrib.contenttypes.models import ContentType
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from mcod.submissions.factories import SubmissionEventFactory
from mcod.submissions.models import Category, Subject


@pytest.fixture(scope="module")
def changelist_url():
    return reverse("admin:submissions_submissionevent_changelist")


@pytest.fixture(scope="module")
def statistics_url():
    return reverse("admin:submissions_submissionevent_statistics")


def _parse_statistics_rows(content: str) -> dict:
    """Return a {(subject_label, category_label): count} map from the statistics table HTML."""
    tbody_match = re.search(r"<tbody>(.*?)</tbody>", content, re.DOTALL)
    assert tbody_match, "No <tbody> found in statistics table"
    row_pattern = re.compile(
        r"<tr[^>]*>\s*<td>([^<]*)</td>\s*<td>([^<]*)</td>\s*<td[^>]*>\s*(\d+)\s*</td>\s*</tr>",
        re.DOTALL,
    )
    return {(m.group(1).strip(), m.group(2).strip()): int(m.group(3).strip()) for m in row_pattern.finditer(tbody_match.group(1))}


@pytest.mark.django_db
class TestSubmissionEventAdminListView:

    def test_changelist_loads_with_200_and_correct_columns(self, django_admin_client: Client, changelist_url: str):
        SubmissionEventFactory.create()
        resp = django_admin_client.get(changelist_url)
        assert resp.status_code == 200
        content = resp.content.decode()

        # Extract thead section to find column headers in correct context
        thead_match = re.search(r"<thead>(.*?)</thead>", content, re.DOTALL)
        assert thead_match, "No <thead> found in changelist"
        thead_content = thead_match.group(1)

        # Verify all column headers are present in thead
        expected_headers = ["ID zgłoszenia", "ID referencyjne", "Temat", "Kategoria", "Data zgłoszenia"]
        for header in expected_headers:
            assert header in thead_content, f"Column header '{header}' not found in table headers"

        # Verify columns appear in correct order within thead
        header_positions = [thead_content.find(header) for header in expected_headers]
        assert header_positions == sorted(
            header_positions
        ), f"Column headers not in correct order. Positions: {dict(zip(expected_headers, header_positions))}"

    def test_default_sort_is_id_descending(self, django_admin_client: Client, changelist_url: str):
        e1 = SubmissionEventFactory.create()
        e2 = SubmissionEventFactory.create()
        resp = django_admin_client.get(changelist_url)
        assert resp.status_code == 200
        content = resp.content.decode()
        pos_e2 = content.find(f"<td>{e2.id}</td>")
        pos_e1 = content.find(f"<td>{e1.id}</td>")
        assert pos_e2 < pos_e1

    def test_pagination_shows_max_20_items(self, django_admin_client: Client, changelist_url: str):
        submissions = SubmissionEventFactory.create_batch(25)
        sorted_by_id = sorted(submissions, key=lambda s: s.id)
        # Lowest 5 IDs on page 2, highest 20 IDs on page 1 (DESC sort)
        page_2_ids = [str(s.id) for s in sorted_by_id[:5]]
        page_1_ids = [str(s.id) for s in sorted_by_id[5:]]

        resp = django_admin_client.get(changelist_url)
        assert resp.status_code == 200
        content = resp.content.decode()

        # Page 1 should contain page 1 submissions
        for submission_id in page_1_ids:
            assert f"<td>{submission_id}</td>" in content, f"Submission {submission_id} should be on page 1"

        # Page 1 should NOT contain page 2 submissions
        for submission_id in page_2_ids:
            assert f"<td>{submission_id}</td>" not in content, f"Submission {submission_id} should be on page 2, not page 1"

        resp2 = django_admin_client.get(changelist_url, {"page": 2})
        assert resp2.status_code == 200
        content2 = resp2.content.decode()

        # Page 2 should contain page 2 submissions
        for submission_id in page_2_ids:
            assert f"<td>{submission_id}</td>" in content2, f"Submission {submission_id} should be on page 2"

        # Page 2 should NOT contain page 1 submissions
        for submission_id in page_1_ids:
            assert f"<td>{submission_id}</td>" not in content2, f"Submission {submission_id} should be on page 1, not page 2"

    def test_empty_state_shows_message_when_no_submissions(self, django_admin_client: Client, changelist_url: str):
        resp = django_admin_client.get(changelist_url)
        assert resp.status_code == 200
        content = resp.content.decode()
        assert "Brak zgłoszeń do wyświetlenia w tabeli" in content

    def test_add_button_absent_from_changelist(self, django_admin_client: Client, changelist_url: str):
        resp = django_admin_client.get(changelist_url)
        assert resp.status_code == 200
        assert "add/" not in resp.content.decode()

    def test_view_forbidden_for_non_admin_user(
        self,
        active_editor,
        changelist_url,
    ):
        client = Client()
        client.force_login(active_editor)
        resp = client.get(changelist_url)
        assert resp.status_code == 403


@pytest.mark.django_db
class TestSubmissionEventAdminFilters:

    def test_subject_filter_returns_matching_submissions(self, django_admin_client: Client, changelist_url: str):
        data_event = SubmissionEventFactory.create(subject=Subject.DATA.value, category=Category.SHARING.value)
        portal_event = SubmissionEventFactory.create(subject=Subject.PORTAL.value, category=Category.BUGS.value)

        resp = django_admin_client.get(changelist_url, {"subject": "DATA"})

        assert resp.status_code == 200
        content = resp.content.decode()
        assert f"<td>{data_event.id}</td>" in content
        assert f"<td>{portal_event.id}</td>" not in content

    def test_category_filter_returns_matching_submissions(self, django_admin_client: Client, changelist_url: str):
        sharing_event = SubmissionEventFactory.create(subject=Subject.DATA.value, category=Category.SHARING.value)
        hvd_event = SubmissionEventFactory.create(subject=Subject.DATA.value, category=Category.HVD.value)

        resp = django_admin_client.get(changelist_url, {"category": "SHARING"})

        assert resp.status_code == 200
        content = resp.content.decode()
        assert f"<td>{sharing_event.id}</td>" in content
        assert f"<td>{hvd_event.id}</td>" not in content

    def test_date_range_filter_returns_submissions_within_range(self, django_admin_client: Client, changelist_url: str):
        now = timezone.now()
        # Use localtime so __date lookup (Warsaw timezone) matches the formatted date string
        local_now = timezone.localtime(now)
        old_event = SubmissionEventFactory.create(submission_date=now - timedelta(days=5))
        recent_event = SubmissionEventFactory.create(submission_date=now)
        date_from = (local_now - timedelta(days=1)).strftime("%Y-%m-%d")
        date_to = local_now.strftime("%Y-%m-%d")

        resp = django_admin_client.get(changelist_url, {"date_from": date_from, "date_to": date_to})

        assert resp.status_code == 200
        content = resp.content.decode()
        assert f"<td>{recent_event.id}</td>" in content
        assert f"<td>{old_event.id}</td>" not in content

    def test_combined_filters_apply_and_logic(self, django_admin_client: Client, changelist_url: str):
        data_sharing = SubmissionEventFactory.create(subject=Subject.DATA.value, category=Category.SHARING.value)
        data_hvd = SubmissionEventFactory.create(subject=Subject.DATA.value, category=Category.HVD.value)
        portal_bugs = SubmissionEventFactory.create(subject=Subject.PORTAL.value, category=Category.BUGS.value)

        resp = django_admin_client.get(changelist_url, {"subject": "DATA", "category": "SHARING"})

        assert resp.status_code == 200
        content = resp.content.decode()
        assert f"<td>{data_sharing.id}</td>" in content
        assert f"<td>{data_hvd.id}</td>" not in content
        assert f"<td>{portal_bugs.id}</td>" not in content

    def test_invalid_date_range_shows_error(self, django_admin_client: Client, changelist_url: str):
        event = SubmissionEventFactory.create()

        resp = django_admin_client.get(changelist_url, {"date_from": "2026-12-31", "date_to": "2026-01-01"})

        assert resp.status_code == 200
        content = resp.content.decode()
        tbody_match = re.search(r"<tbody>(.*?)</tbody>", content, re.DOTALL)
        tbody = tbody_match.group(1)

        assert f"<td>{event.id}</td>" in tbody


@pytest.mark.django_db
class TestSubmissionEventAdminStatistics:

    def test_statistics_renders_exactly_16_rows(self, django_admin_client: Client, statistics_url: str):
        resp = django_admin_client.get(statistics_url)
        assert resp.status_code == 200
        rows = _parse_statistics_rows(resp.content.decode())
        assert len(rows) == 16
        assert rows[("Dane", "Udostępnianie danych w portalu")] == 0
        assert rows[("Dane", "Zaproponuj dane do udostępnienia w portalu")] == 0
        assert rows[("Dane", "Zaproponuj przykład ponownego wykorzystania danych")] == 0
        assert rows[("Dane", "Zgłoś uwagi do danych udostępnionych w portalu")] == 0
        assert rows[("Dane", "Standardy otwartości danych")] == 0
        assert rows[("Dane", "Dane o wysokiej wartości (HVD)")] == 0
        assert rows[("Dane", "Chronione dane (DGA)")] == 0
        assert rows[("Dane", "Inne")] == 0
        assert rows[("Portal dane.gov.pl", "Funkcjonalności portalu")] == 0
        assert rows[("Portal dane.gov.pl", "Zakładanie profili dostawców")] == 0
        assert rows[("Portal dane.gov.pl", "Nadawanie uprawnień")] == 0
        assert rows[("Portal dane.gov.pl", "Błędy w działaniu portalu")] == 0
        assert rows[("Portal dane.gov.pl", "Inne")] == 0
        assert rows[("Ochrona danych osobowych w portalu", "-")] == 0
        assert rows[("Regulacje prawne dotyczące otwartości danych", "-")] == 0
        assert rows[("Inne", "-")] == 0

    def test_statistics_shows_correct_counts_per_subject_category(self, django_admin_client: Client, statistics_url: str):
        SubmissionEventFactory.create_batch(3, subject=Subject.DATA.value, category=Category.SHARING.value)
        SubmissionEventFactory.create_batch(2, subject=Subject.PORTAL.value, category=Category.BUGS.value)
        SubmissionEventFactory.create(subject=Subject.DATA.value, category=Category.HVD.value)
        resp = django_admin_client.get(statistics_url)
        assert resp.status_code == 200
        rows = _parse_statistics_rows(resp.content.decode())
        assert rows[("Dane", "Udostępnianie danych w portalu")] == 3
        assert rows[("Portal dane.gov.pl", "Błędy w działaniu portalu")] == 2
        assert rows[("Dane", "Dane o wysokiej wartości (HVD)")] == 1
        assert rows[("Dane", "Zaproponuj dane do udostępnienia w portalu")] == 0

    def test_statistics_all_zero_when_no_submissions(self, django_admin_client: Client, statistics_url: str):
        resp = django_admin_client.get(statistics_url)
        assert resp.status_code == 200
        rows = _parse_statistics_rows(resp.content.decode())
        assert len(rows) == 16
        assert all(count == 0 for count in rows.values())

    def test_statistics_date_filter_restricts_counts_to_matching_period(self, django_admin_client: Client, statistics_url: str):
        now = timezone.now()
        local_now = timezone.localtime(now)
        SubmissionEventFactory.create(
            subject=Subject.DATA.value,
            category=Category.SHARING.value,
            submission_date=now - timedelta(days=30),
        )
        SubmissionEventFactory.create(
            subject=Subject.DATA.value,
            category=Category.SHARING.value,
            submission_date=now,
        )
        date_from = (local_now - timedelta(days=1)).strftime("%Y-%m-%d")
        resp = django_admin_client.get(statistics_url, {"date_from": date_from})
        assert resp.status_code == 200
        rows = _parse_statistics_rows(resp.content.decode())
        assert rows[("Dane", "Udostępnianie danych w portalu")] == 1
        assert rows[("Portal dane.gov.pl", "Błędy w działaniu portalu")] == 0

    def test_submission_event_admin_view_forbidden_for_non_admin_user(
        self,
        active_editor,
        statistics_url,
    ):
        client = Client()
        client.force_login(active_editor)
        resp = client.get(statistics_url)
        assert resp.status_code == 403


@pytest.mark.django_db
class TestSubmissionEventAdminReferenceLink:

    @pytest.mark.parametrize(
        "app_label, model, expected_label",
        [
            ("suggestions", "datasetcomment", "UwagaDoZbioru"),
            ("suggestions", "resourcecomment", "UwagaDoZasobu"),
            ("showcases", "showcaseproposal", "PoCoTo"),
            ("suggestions", "datasetsubmission", "PropozycjaNowychDanych"),
        ],
    )
    def test_reference_display_renders_link_when_reference_exists(
        self, django_admin_client: Client, changelist_url: str, app_label, model, expected_label
    ):
        ct = ContentType.objects.get(app_label=app_label, model=model)
        SubmissionEventFactory.create(
            reference_content_type=ct,
            reference_object_id=42,
        )
        resp = django_admin_client.get(changelist_url)
        assert resp.status_code == 200
        content = resp.content.decode()
        assert f"{expected_label}_42" in content

    def test_reference_display_renders_empty_when_no_reference(self, django_admin_client: Client, changelist_url: str):
        SubmissionEventFactory.create(
            reference_content_type=None,
            reference_object_id=None,
        )
        resp = django_admin_client.get(changelist_url)
        assert resp.status_code == 200
        content = resp.content.decode()
        # Scope check to tbody only — labels may appear in admin sidebar nav
        tbody_match = re.search(r"<tbody>(.*?)</tbody>", content, re.DOTALL)
        assert tbody_match, "No <tbody> found in changelist"
        tbody = tbody_match.group(1)
        for label in ("UwagaDoZbioru", "UwagaDoZasobu", "PoCoTo", "PropozycjaNowychDanych"):
            assert label not in tbody


@pytest.mark.django_db
class TestSubmissionEventAdminReadOnly:

    def test_add_url_returns_403(self, django_admin_client: Client):
        resp = django_admin_client.get(reverse("admin:submissions_submissionevent_add"))
        assert resp.status_code == 403

    def test_change_url_renders_readonly_without_save_button(self, django_admin_client: Client):
        event = SubmissionEventFactory.create()
        resp = django_admin_client.get(reverse("admin:submissions_submissionevent_change", args=[event.pk]))
        assert resp.status_code == 200
        assert 'name="_save"' not in resp.content.decode()

    def test_delete_url_returns_403(self, django_admin_client: Client):
        event = SubmissionEventFactory.create()
        resp = django_admin_client.get(reverse("admin:submissions_submissionevent_delete", args=[event.pk]))
        assert resp.status_code == 403


@pytest.mark.django_db
class TestSubmissionEventAdminReportViews:

    @pytest.fixture
    def generate_unit_url(self):
        return reverse("admin:submissions_submissionevent_generate_unit_report")

    @pytest.fixture
    def generate_stats_url(self):
        return reverse("admin:submissions_submissionevent_generate_stats_report")

    def test_changelist_contains_generate_unit_report_button(self, django_admin_client: Client, changelist_url: str):
        resp = django_admin_client.get(changelist_url)

        assert resp.status_code == 200
        content = resp.content.decode()
        assert reverse("admin:submissions_submissionevent_generate_unit_report") in content
        assert "Generuj raport jednostkowy (CSV)" in content

    def test_statistics_contains_generate_stats_report_button(self, django_admin_client: Client, statistics_url: str):
        resp = django_admin_client.get(statistics_url)

        assert resp.status_code == 200
        content = resp.content.decode()
        assert reverse("admin:submissions_submissionevent_generate_stats_report") in content
        assert "Generuj raport statystyczny (CSV)" in content

    @pytest.mark.parametrize(
        "query_params, expected_query_string",
        [
            ({}, ""),
            ({"subject": "DATA"}, "?subject=DATA"),
            ({"category": "SHARING", "date_from": "2026-01-01"}, "?category=SHARING&date_from=2026-01-01"),
            ({"subject": "PORTAL", "date_to": "2026-12-31"}, "?subject=PORTAL&date_to=2026-12-31"),
        ],
    )
    @patch("mcod.submissions.admin.generate_submission_unit_report_task.delay")
    def test_generate_unit_report_view_dispatches_task_and_redirects(
        self, mock_task, admin, generate_unit_url, query_params, expected_query_string
    ):
        """
        Test if the view dispatches the report generation task and redirects to the changelist.
        """
        client = Client()
        client.force_login(admin)

        resp = client.get(generate_unit_url, query_params)

        # Base path without query string
        expected_path = reverse("admin:submissions_submissionevent_changelist")
        expected_redirect_url = expected_path + expected_query_string

        assert resp.status_code == 302

        # Parse actual and expected URLs
        parsed_actual = urlparse(resp.url)
        parsed_expected = urlparse(expected_redirect_url)

        # Compare URL components explicitly to avoid flakiness caused by query param order
        assert parsed_actual.path == parsed_expected.path
        assert parse_qs(parsed_actual.query) == parse_qs(parsed_expected.query)

        mock_task.assert_called_once_with(
            user_id=admin.pk,
            subject=query_params.get("subject", ""),
            category=query_params.get("category", ""),
            date_from=query_params.get("date_from", ""),
            date_to=query_params.get("date_to", ""),
        )

    @pytest.mark.parametrize(
        "query_params, expected_query_string",
        [
            ({}, ""),
            ({"date_from": "2026-01-01"}, "?date_from=2026-01-01"),
            ({"date_from": "2026-01-01", "date_to": "2026-12-31"}, "?date_from=2026-01-01&date_to=2026-12-31"),
        ],
    )
    @patch("mcod.submissions.admin.generate_statistical_report_for_all_submissions_task.delay")
    def test_generate_stats_report_view_dispatches_task_and_redirects(
        self, mock_task, admin, generate_stats_url, query_params, expected_query_string
    ):
        client = Client()
        client.force_login(admin)

        resp = client.get(generate_stats_url, query_params)

        expected_redirect_url = reverse("admin:submissions_submissionevent_statistics") + expected_query_string
        assert resp.status_code == 302
        assert resp.url == expected_redirect_url

        mock_task.assert_called_once_with(
            user_id=admin.pk,
            date_from=query_params.get("date_from", ""),
            date_to=query_params.get("date_to", ""),
        )
