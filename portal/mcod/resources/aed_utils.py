"""Wykaz zbiorczy AED – część zależna od modeli portalu (AEDane, HackNation 2026).

Wzór: Wykaz Główny DGA (dga_utils.py). Instytucje publikują zasoby AED w wzorcowym zakresie
danych i oznaczają je flagą `contains_aed_data`; zadanie tasks/aed.py codziennie skleja je
(aed_merge.py) w jeden zasób CSV „Wykaz zbiorczy defibrylatorów AED” w zbiorze instytucji
wskazanej w ustawieniach (MAIN_AED_DATASET_OWNER_ORGANIZATION_PK).
"""

import csv
import datetime
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

import sentry_sdk
from django.apps import apps
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.db.models import QuerySet

from mcod.resources.aed_merge import MAIN_AED_COLUMNS, MissingRequiredColumnsError, merge_sources, missing_required_columns

if TYPE_CHECKING:
    from mcod.resources.models import Dataset, Resource

logger = logging.getLogger("mcod")


def get_main_aed_resource() -> Optional["Resource"]:
    AggregatedAEDInfo = apps.get_model("resources", "AggregatedAEDInfo")
    info = AggregatedAEDInfo.objects.last()
    return info.main_aed_resource if info else None


def get_main_aed_dataset() -> Optional["Dataset"]:
    AggregatedAEDInfo = apps.get_model("resources", "AggregatedAEDInfo")
    info = AggregatedAEDInfo.objects.last()
    return info.main_aed_dataset if info else None


def get_all_aed_resources() -> QuerySet:
    """Opublikowane zasoby z flagą AED i udaną walidacją portalu – jak w DGA (dga_utils.py:234)."""
    Resource = apps.get_model("resources", "Resource")
    main = get_main_aed_resource()
    return (
        Resource.objects.filter(
            contains_aed_data=True,
            status="published",
            data_tasks_last_status="SUCCESS",
            file_tasks_last_status="SUCCESS",
            link_tasks_last_status="SUCCESS",
        )
        .exclude(id=main.pk if main else None)
        .select_related("dataset__organization")
        .order_by("dataset__organization__title")
    )


def read_aed_resource_rows(resource: "Resource") -> List[Dict]:
    """Wiersze zasobu z danych tabelarycznych portalu (tak samo jak DGA: tabular_data.table.read)."""
    data = resource.tabular_data.table.read(keyed=True)
    rows = [dict(r) for r in data]
    if rows:
        missing = missing_required_columns(rows[0].keys())
        if missing:
            raise MissingRequiredColumnsError(missing)
    return rows


def create_main_aed_rows(resources: QuerySet) -> Tuple[List[Dict], List[Dict]]:
    """Scala zasoby; zasób, którego nie da się przeczytać, pomija z logiem (nie przerywa całości)."""
    sources = []
    for resource in resources:
        try:
            rows = read_aed_resource_rows(resource)
        except MissingRequiredColumnsError as exc:
            logger.error("Pomijam zasób AED %s: %s", resource.pk, exc)
            continue
        except Exception as exc:  # noqa: BLE001 – jak w DGA: błąd jednego zasobu nie zatrzymuje wykazu
            sentry_sdk.api.capture_exception(exc)
            logger.error("Pomijam zasób AED %s – nie da się go przeczytać: %s", resource.pk, exc)
            continue
        sources.append((resource.institution.title, resource.pk, rows))
    merged, skipped = merge_sources(sources)
    logger.info("Wykaz zbiorczy AED: %s zasobów, %s AED, %s pominiętych wierszy.", len(sources), len(merged), len(skipped))
    return merged, skipped


def create_main_aed_file() -> Path:
    directory = Path(settings.MAIN_AED_RESOURCE_CSV_CREATION_ROOT)
    directory.mkdir(parents=True, exist_ok=True)
    today = datetime.datetime.now().strftime("%Y%m%d")
    path = directory / f"{settings.MAIN_AED_CSV_FILE_NAME_PREFIX} {today}.csv"
    rows, _ = create_main_aed_rows(get_all_aed_resources())
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=MAIN_AED_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return path


def create_main_aed_dataset() -> int:
    """Zbiór „Wykaz zbiorczy defibrylatorów AED” instytucji z MAIN_AED_DATASET_OWNER_ORGANIZATION_PK."""
    Organization = apps.get_model("organizations", "Organization")
    Dataset = apps.get_model("datasets", "Dataset")
    Category = apps.get_model("categories", "Category")
    try:
        institution = Organization.objects.get(pk=settings.MAIN_AED_DATASET_OWNER_ORGANIZATION_PK)
    except Organization.DoesNotExist:
        logger.error("Nie ma instytucji %s – właściciela wykazu AED.", settings.MAIN_AED_DATASET_OWNER_ORGANIZATION_PK)
        raise ObjectDoesNotExist("Main AED owner institution not found.")
    with transaction.atomic():
        dataset = Dataset.objects.create(
            title=settings.MAIN_AED_DATASET_DEFAULT_TITLE,
            notes=settings.MAIN_AED_DATASET_DEFAULT_DESC,
            organization=institution,
            has_dynamic_data=False,
            has_high_value_data=False,
            has_high_value_data_from_ec_list=False,
            has_research_data=False,
            update_frequency="daily",
            status="published",
        )
        dataset.categories.set(Category.objects.filter(code__in=settings.MAIN_AED_DATASET_CATEGORY_CODES))
        dataset.save()
    logger.info("Utworzono zbiór wykazu AED %s.", dataset.pk)
    return dataset.pk


def create_main_aed_resource_with_dataset(file_path: Path) -> Tuple[int, Optional[int]]:
    """Zasób CSV wykazu AED (i zbiór, jeśli go nie ma). Zwraca (pk zasobu, pk nowego zbioru albo None)."""
    Resource = apps.get_model("resources", "Resource")
    ResourceFile = apps.get_model("resources", "ResourceFile")
    Dataset = apps.get_model("datasets", "Dataset")
    old_resource = get_main_aed_resource()
    dataset = get_main_aed_dataset()
    new_dataset = False
    with transaction.atomic():
        if dataset is None:
            dataset = Dataset.objects.get(pk=create_main_aed_dataset())
            new_dataset = True
        resource = Resource.objects.create(
            title=old_resource.title if old_resource else settings.MAIN_AED_RESOURCE_DEFAULT_TITLE,
            description=old_resource.description if old_resource else settings.MAIN_AED_RESOURCE_DEFAULT_DESC,
            dataset=dataset,
            has_dynamic_data=False,
            has_high_value_data=False,
            has_high_value_data_from_ec_list=False,
            has_research_data=False,
            # Sam wykaz nie jest źródłem wykazu – bez flagi, żeby nie scalał sam siebie.
            contains_aed_data=False,
            status="published",
            data_date=datetime.datetime.today(),
        )
        with open(file_path, "rb") as fh:
            django_file = SimpleUploadedFile(name=os.path.basename(file_path), content=fh.read(), content_type="text/csv")
        # post_save uruchamia walidację pliku, danych i linku – jak dla każdego zasobu.
        ResourceFile.objects.create(resource=resource, is_main=True, file=django_file)
    return resource.pk, dataset.pk if new_dataset else None


def update_aggregated_aed_info(new_resource: "Resource") -> None:
    """Wskazuje nowy zasób wykazu i usuwa poprzedni (jak update_or_create_aggr_dga_info_...)."""
    AggregatedAEDInfo = apps.get_model("resources", "AggregatedAEDInfo")
    info = AggregatedAEDInfo.objects.last()
    old_resource = info.main_aed_resource if info else None
    with transaction.atomic():
        if info:
            info.resource = new_resource
            info.save()
        else:
            AggregatedAEDInfo.objects.create(resource=new_resource)
        if old_resource:
            old_resource.delete()


def clean_up_main_aed(resource_pk: Optional[int], dataset_pk: Optional[int], file_path: Optional[Path]) -> None:
    """Po błędzie usuwa utworzone obiekty; zawsze usuwa plik tymczasowy."""
    Resource = apps.get_model("resources", "Resource")
    Dataset = apps.get_model("datasets", "Dataset")
    try:
        if resource_pk:
            Resource.raw.filter(pk=resource_pk).delete()
        if dataset_pk:
            Dataset.raw.filter(pk=dataset_pk).delete()
    except Exception as exc:  # noqa: BLE001
        logger.error("Sprzątanie po wykazie AED nie powiodło się: %s", exc)
        sentry_sdk.api.capture_exception(exc)
    if file_path and os.path.exists(file_path):
        os.remove(file_path)
