import datetime
from typing import Dict, List, Optional, Tuple

from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Page, Paginator
from django.db.models import Count, QuerySet
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import NoReverseMatch, path, reverse
from django.utils.html import escape, mark_safe

from mcod.lib.admin_mixins import ModelAdmin
from mcod.submissions.models import (
    CATEGORY_CHOICES,
    CONTENT_TYPE_TO_TYPE_LABEL,
    SUBJECT_CATEGORY_DEPENDENCIES,
    SUBJECT_CHOICES,
    SubmissionEvent,
)
from mcod.submissions.tasks import (
    generate_statistical_report_for_all_submissions_task,
    generate_submission_unit_report_task,
)

_PAGE_SIZE = 20


@admin.register(SubmissionEvent)
class SubmissionEventAdmin(ModelAdmin):
    """Read-only admin view for submission events with unit list and statistics tabs."""

    actions = None

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Optional[SubmissionEvent] = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Optional[SubmissionEvent] = None) -> bool:
        return False

    def has_view_permission(self, request: HttpRequest, obj: Optional[SubmissionEvent] = None) -> bool:
        return request.user.is_superuser

    def get_urls(self) -> list:
        urls = super().get_urls()
        custom_urls = [
            path(
                "statistics/",
                self.admin_site.admin_view(self.statistics_view),
                name="submissions_submissionevent_statistics",
            ),
            path(
                "generate_unit_report/",
                self.admin_site.admin_view(self.generate_unit_report_view),
                name="submissions_submissionevent_generate_unit_report",
            ),
            path(
                "generate_stats_report/",
                self.admin_site.admin_view(self.generate_stats_report_view),
                name="submissions_submissionevent_generate_stats_report",
            ),
        ]
        return custom_urls + urls

    def generate_stats_report_view(self, request: HttpRequest) -> HttpResponseRedirect:
        date_from = request.GET.get("date_from", "")
        date_to = request.GET.get("date_to", "")
        generate_statistical_report_for_all_submissions_task.delay(
            user_id=request.user.pk,
            date_from=date_from,
            date_to=date_to,
        )
        messages.info(
            request,
            "Zadanie generowania raportu statystycznego zostało zlecone. Raport będzie dostępny w sekcji Raporty → Zgłoszenia.",
        )
        query_string = request.GET.urlencode()
        redirect_url = reverse("admin:submissions_submissionevent_statistics")
        if query_string:
            redirect_url = f"{redirect_url}?{query_string}"
        return HttpResponseRedirect(redirect_url)

    def generate_unit_report_view(self, request: HttpRequest) -> HttpResponseRedirect:
        subject = request.GET.get("subject", "")
        category = request.GET.get("category", "")
        date_from = request.GET.get("date_from", "")
        date_to = request.GET.get("date_to", "")
        task_kwargs = {
            "user_id": request.user.pk,
            "subject": subject,
            "category": category,
            "date_from": date_from,
            "date_to": date_to,
        }
        generate_submission_unit_report_task.delay(**task_kwargs)

        messages.info(
            request,
            "Zadanie generowania raportu jednostkowego zostało zlecone. Raport będzie dostępny w sekcji Raporty → Zgłoszenia.",
        )
        query_string = request.GET.urlencode()
        redirect_url = reverse("admin:submissions_submissionevent_changelist")
        if query_string:
            redirect_url = f"{redirect_url}?{query_string}"
        return HttpResponseRedirect(redirect_url)

    def _tab_context(self) -> Dict[str, str]:
        return {
            "unit_url": reverse("admin:submissions_submissionevent_changelist"),
            "statistics_url": reverse("admin:submissions_submissionevent_statistics"),
        }

    def _parse_dates(
        self, request: HttpRequest
    ) -> Tuple[str, str, Optional[datetime.date], Optional[datetime.date], Optional[str]]:
        """Parse and validate date_from/date_to from GET params."""
        date_from_str = request.GET.get("date_from", "")
        date_to_str = request.GET.get("date_to", "")
        date_from = None
        date_to = None
        date_error = None

        try:
            if date_from_str:
                date_from = datetime.date.fromisoformat(date_from_str)
            if date_to_str:
                date_to = datetime.date.fromisoformat(date_to_str)
            if date_from and date_to and date_from > date_to:
                date_error = "'Data od' musi być wcześniejsza lub równa 'Data do'."
        except ValueError:
            date_error = "Nieprawidłowy format daty."

        if date_error:
            date_from = date_to = None

        return date_from_str, date_to_str, date_from, date_to, date_error

    def _get_sorting_params(self, request: HttpRequest) -> Tuple[str, str, str]:
        """Extract and validate sorting parameters from the request."""
        sort_field = request.GET.get("o", "id")
        sort_dir = request.GET.get("dir", "desc")
        allowed_sort_fields = {"id", "subject", "category", "submission_date"}

        if sort_field not in allowed_sort_fields:
            sort_field = "id"
        if sort_dir not in ("asc", "desc"):
            sort_dir = "desc"

        order_prefix = "" if sort_dir == "asc" else "-"
        return sort_field, sort_dir, f"{order_prefix}{sort_field}"

    def _get_filtered_queryset(
        self, ordering: str, date_from: Optional[datetime.date], date_to: Optional[datetime.date], subject: str, category: str
    ) -> QuerySet:
        """Build and filter the queryset based on provided parameters."""
        qs = SubmissionEvent.objects.select_related("reference_content_type").order_by(ordering)

        if date_from:
            qs = qs.filter(submission_date__date__gte=date_from)
        if date_to:
            qs = qs.filter(submission_date__date__lte=date_to)
        if subject:
            qs = qs.filter(subject=subject)
        if category:
            qs = qs.filter(category=category)

        return qs

    def _build_rows(self, page_obj: Page) -> List[dict]:
        """Convert page objects into display row dictionaries."""
        return [
            {
                "id": event.id,
                "reference_display": self._build_reference_display(event),
                "subject": event.display_subject,
                "category": event.display_category,
                "submission_date": event.submission_date,
            }
            for event in page_obj
        ]

    def changelist_view(self, request: HttpRequest, extra_context: Optional[dict] = None) -> HttpResponse:
        if not self.has_view_permission(request):
            raise PermissionDenied

        date_from_str, date_to_str, date_from, date_to, date_error = self._parse_dates(request)
        if date_error:
            messages.error(request, date_error)
            date_from, date_to = None, None  # Prevent filtering if there is a date error

        subject = request.GET.get("subject", "")
        category = request.GET.get("category", "")
        sort_field, sort_dir, ordering = self._get_sorting_params(request)

        qs = self._get_filtered_queryset(
            ordering=ordering,
            date_from=date_from,
            date_to=date_to,
            subject=subject,
            category=category,
        )

        paginator = Paginator(qs, _PAGE_SIZE)
        page_number = request.GET.get("page", 1)
        page_obj = paginator.get_page(page_number)

        context = {
            **self.admin_site.each_context(request),
            **self._tab_context(),
            "title": "Wszystkie zgłoszenia",
            "opts": self.model._meta,
            "app_label": self.model._meta.app_label,
            "active_tab": "unit",
            "rows": self._build_rows(page_obj),
            "page_obj": page_obj,
            "paginator": paginator,
            "page_range": self._build_page_range(page_obj.number, paginator.num_pages),
            "date_from": date_from_str,
            "date_to": date_to_str,
            "subject": subject,
            "category": category,
            "subject_choices": [(s.value, label) for s, label in SUBJECT_CHOICES],
            "category_choices": [(c.value, label) for c, label in CATEGORY_CHOICES],
            "sort_field": sort_field,
            "sort_dir": sort_dir,
            **(extra_context or {}),
        }
        return render(request, "admin/submissions/submissionevent/change_list.html", context)

    def statistics_view(self, request: HttpRequest) -> HttpResponse:
        """Render the aggregated statistics view."""
        if not self.has_view_permission(request):
            raise PermissionDenied

        date_from_str, date_to_str, date_from, date_to, date_error = self._parse_dates(request)

        qs = SubmissionEvent.objects.all()
        if date_error:
            messages.error(request, date_error)
        else:
            if date_from:
                qs = qs.filter(submission_date__date__gte=date_from)
            if date_to:
                qs = qs.filter(submission_date__date__lte=date_to)

        counts = qs.values("subject", "category").annotate(count=Count("id"))
        count_map: Dict[Tuple[str, str], int] = {(row["subject"], row["category"]): row["count"] for row in counts}

        subject_labels = dict(SUBJECT_CHOICES)
        category_labels = dict(CATEGORY_CHOICES)

        rows: List[dict] = []
        for subject_enum, categories in SUBJECT_CATEGORY_DEPENDENCIES.items():
            if categories:
                for cat in categories:
                    rows.append(
                        {
                            "subject": subject_labels.get(subject_enum, subject_enum.value),
                            "category": category_labels.get(cat, cat.value),
                            "count": count_map.get((subject_enum.value, cat.value), 0),
                        }
                    )
            else:
                rows.append(
                    {
                        "subject": subject_labels.get(subject_enum, subject_enum.value),
                        "category": "-",
                        "count": count_map.get((subject_enum.value, ""), 0),
                    }
                )

        context = {
            **self.admin_site.each_context(request),
            **self._tab_context(),
            "title": "Wszystkie zgłoszenia — Statystyki",
            "opts": self.model._meta,
            "app_label": self.model._meta.app_label,
            "active_tab": "statistics",
            "rows": rows,
            "date_from": date_from_str,
            "date_to": date_to_str,
        }
        return render(request, "admin/submissions/submissionevent/statistics.html", context)

    @staticmethod
    def _build_reference_display(event: SubmissionEvent) -> str:
        if not event.reference_content_type_id or not event.reference_object_id:
            return ""

        ct = event.reference_content_type
        key = (ct.app_label, ct.model)
        type_label = CONTENT_TYPE_TO_TYPE_LABEL.get(key)
        if not type_label:
            return ""

        display_text = f"{type_label}_{event.reference_object_id}"
        try:
            url = reverse(f"admin:{ct.app_label}_{ct.model}_change", args=[event.reference_object_id])
        except NoReverseMatch:
            return display_text
        return mark_safe(f'<a href="{escape(url)}">{escape(display_text)}</a>')

    @staticmethod
    def _build_page_range(current: int, total: int) -> List:
        """Build page numbers with '...' as ellipsis placeholder."""
        if total <= 4:
            return list(range(1, total + 1))
        pages: List = []
        for num in range(1, total + 1):
            if num == 1 or num == total or abs(num - current) <= 2:
                pages.append(num)
            elif pages and pages[-1] != "...":
                pages.append("...")
        return pages
