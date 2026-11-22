import csv
import json
import logging
from datetime import date
from pathlib import Path
from smtplib import SMTPException
from time import time
from typing import Any, Dict, Optional

from celery.signals import task_prerun, task_success
from constance import config
from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.db.models import Count
from django.template.loader import render_to_string
from django.urls import NoReverseMatch, reverse
from django.utils.timezone import localtime, now
from django_celery_results.models import TaskResult

from mcod.core.tasks import extended_shared_task
from mcod.reports.models import Report
from mcod.submissions.attachments import AttachmentStagingManager
from mcod.submissions.models import (
    CATEGORY_CHOICES,
    CONTENT_TYPE_TO_TYPE_LABEL,
    SUBJECT_CATEGORY_DEPENDENCIES,
    SUBJECT_CHOICES,
    SubmissionEvent,
)
from mcod.submissions.service import build_email_subject
from mcod.users.models import User

logger = logging.getLogger(__name__)


@extended_shared_task(
    max_retries=settings.GENERIC_SUBMISSION_EMAIL_MAX_RETRIES,
    retry_on_errors=(SMTPException,),
    retry_countdown=settings.GENERIC_SUBMISSION_EMAIL_RETRY_DELAY,
)
def send_generic_submission_email_task(
    event_id: int,
    content: str,
    applicant_full_name: Optional[str],
    applicant_email: Optional[str],
) -> Dict[str, Any]:
    event: SubmissionEvent = SubmissionEvent.objects.get(pk=event_id)

    context = {
        "host": settings.BASE_URL,
        "event_id": event_id,
        "submission_date": localtime(event.submission_date).strftime("%Y-%m-%d %H:%M"),
        "subject_display": event.get_subject_display(),
        "category_display": event.get_category_display() or "",
        "applicant_full_name": applicant_full_name,
        "applicant_email": applicant_email,
        "content": content,
    }

    from_email = config.NO_REPLY_EMAIL
    to = [config.TESTER_EMAIL] if settings.DEBUG and config.TESTER_EMAIL else [config.CONTACT_MAIL]

    mail = EmailMultiAlternatives(
        subject=build_email_subject(event.display_category if event.category else event.display_subject, event),
        body=render_to_string("mails/generic-submission.txt", context),
        from_email=from_email,
        to=to,
        connection=get_connection(settings.EMAIL_BACKEND),
    )
    mail.mixed_subtype = "related"
    mail.attach_alternative(render_to_string("mails/generic-submission.html", context), "text/html")

    staging = AttachmentStagingManager()
    for attachment in staging.load(event_id):
        mail.attach(attachment.filename, attachment.content, attachment.mime_type)

    logger.info(f"Sending generic submission email for event_id={event_id}")
    mail.send()
    staging.cleanup(event_id)

    return {"sent": True, "event_id": event_id}


def _build_reference_id(event: SubmissionEvent) -> str:
    if not event.reference_content_type_id or not event.reference_object_id:
        return ""
    ct = event.reference_content_type
    type_label = CONTENT_TYPE_TO_TYPE_LABEL.get((ct.app_label, ct.model))
    if not type_label:
        return ""
    return f"{type_label}_{event.reference_object_id}"


def _build_reference_url(event: SubmissionEvent) -> str:
    if not event.reference_content_type_id or not event.reference_object_id:
        return ""
    ct = event.reference_content_type
    if not CONTENT_TYPE_TO_TYPE_LABEL.get((ct.app_label, ct.model)):
        return ""
    try:
        path = reverse(f"admin:{ct.app_label}_{ct.model}_change", args=[event.reference_object_id])
    except NoReverseMatch:
        return ""
    return f"{settings.ADMIN_URL}{path}"


@extended_shared_task(ignore_result=False)
def generate_submission_unit_report_task(
    *,
    user_id: int,
    subject: str,
    category: str,
    date_from: str,
    date_to: str,
) -> str:
    qs = SubmissionEvent.objects.select_related("reference_content_type").order_by("-id")
    if subject:
        qs = qs.filter(subject=subject)
    if category:
        qs = qs.filter(category=category)
    if date_from:
        qs = qs.filter(submission_date__date__gte=date.fromisoformat(date_from))
    if date_to:
        qs = qs.filter(submission_date__date__lte=date.fromisoformat(date_to))

    filename = f"submission_details_{localtime(now()).strftime('%Y%m%d%H%M%S')}.{int(time())}.csv"
    reports_path = Path(settings.REPORTS_MEDIA_ROOT, "submissions")
    reports_path.mkdir(exist_ok=True, parents=True)
    file_path = reports_path / filename

    with file_path.open(mode="w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["ID zgłoszenia", "ID referencyjne", "Link do zgłoszenia", "Temat", "Kategoria", "Data zgłoszenia"])
        for event in qs.iterator(chunk_size=2000):
            writer.writerow(
                [
                    event.id,
                    _build_reference_id(event),
                    _build_reference_url(event),
                    event.display_subject,
                    event.display_category if event.category else "",
                    localtime(event.submission_date).strftime("%Y-%m-%d %H:%M:%S"),
                ]
            )

    return json.dumps(
        {
            "model": "submissions.SubmissionEvent",
            "csv_file": f"{settings.REPORTS_MEDIA}/submissions/{filename}",
            "date": localtime(now()).strftime("%Y.%m.%d %H:%M"),
            "user_email": User.objects.get(pk=user_id).email,
        }
    )


def _build_stats_filename(date_from: str, date_to: str) -> str:
    timestamp = localtime(now()).strftime("%Y%m%d%H%M%S")
    unix_ts = int(time())
    if date_from and date_to:
        from_fmt = date.fromisoformat(date_from).strftime("%Y%m%d")
        to_fmt = date.fromisoformat(date_to).strftime("%Y%m%d")
        return f"submissions_stats_from_{from_fmt}_to_{to_fmt}_{timestamp}.{unix_ts}.csv"
    if date_from:
        from_fmt = date.fromisoformat(date_from).strftime("%Y%m%d")
        return f"submissions_stats_from_{from_fmt}_{timestamp}.{unix_ts}.csv"
    if date_to:
        to_fmt = date.fromisoformat(date_to).strftime("%Y%m%d")
        return f"submissions_stats_to_{to_fmt}_{timestamp}.{unix_ts}.csv"
    return f"submissions_stats_{timestamp}.{unix_ts}.csv"


@extended_shared_task(ignore_result=False)
def generate_statistical_report_for_all_submissions_task(
    *,
    user_id: int,
    date_from: str,
    date_to: str,
) -> str:
    qs = SubmissionEvent.objects.all()
    if date_from:
        qs = qs.filter(submission_date__date__gte=date.fromisoformat(date_from))
    if date_to:
        qs = qs.filter(submission_date__date__lte=date.fromisoformat(date_to))

    count_map = {
        (row["subject"], row["category"]): row["count"] for row in qs.values("subject", "category").annotate(count=Count("id"))
    }

    subject_labels = {k.value: v for k, v in SUBJECT_CHOICES}
    category_labels = {k.value: v for k, v in CATEGORY_CHOICES}

    filename = _build_stats_filename(date_from, date_to)
    reports_path = Path(settings.REPORTS_MEDIA_ROOT, "submissions")
    reports_path.mkdir(exist_ok=True, parents=True)
    file_path = reports_path / filename

    with file_path.open(mode="w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["Temat", "Kategoria", "Liczba zgłoszeń"])
        for subject_enum, categories in SUBJECT_CATEGORY_DEPENDENCIES.items():
            subject_label = subject_labels.get(subject_enum.value, subject_enum.value)
            if categories:
                for cat in categories:
                    category_label = category_labels.get(cat.value, cat.value)
                    writer.writerow([subject_label, category_label, count_map.get((subject_enum.value, cat.value), 0)])
            else:
                writer.writerow([subject_label, "", count_map.get((subject_enum.value, ""), 0)])

    return json.dumps(
        {
            "model": "submissions.SubmissionEvent",
            "csv_file": f"{settings.REPORTS_MEDIA}/submissions/{filename}",
            "date": localtime(now()).strftime("%Y.%m.%d %H:%M"),
            "user_email": User.objects.get(pk=user_id).email,
        }
    )


@task_prerun.connect(sender=generate_submission_unit_report_task)
@task_prerun.connect(sender=generate_statistical_report_for_all_submissions_task)
def generating_submission_report_prerun(sender, task_id, task, signal, **kwargs):
    try:
        user_id = kwargs["kwargs"]["user_id"]
        task_obj = TaskResult.objects.get_task(task_id)
        task_obj.save()
        try:
            ordered_by = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            ordered_by = None
        report = Report(model="submissions.SubmissionEvent", ordered_by=ordered_by, task=task_obj)
        report.save()
    except Exception as e:
        logger.error(f"reports.task: exception on generating_submission_unit_report_prerun:\n{e}")


@task_success.connect(sender=generate_submission_unit_report_task)
@task_success.connect(sender=generate_statistical_report_for_all_submissions_task)
def generating_submission_report_success(sender, result, **kwargs):
    try:
        result_dict = json.loads(result)
        result_task = TaskResult.objects.get_task(sender.request.id)
        result_task.result = result
        result_task.status = "SUCCESS"
        result_task.save()
        report = Report.objects.get(task=result_task)
        report.file = result_dict.get("csv_file")
        report.save()
    except Exception as e:
        logger.error(f"reports.task: exception on generating_submission_unit_report_success:\n{e}")
