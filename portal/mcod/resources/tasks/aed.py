"""Zadanie Celery: wykaz zbiorczy AED (AEDane, HackNation 2026) – na wzór tasks/dga.py.

Prościej niż DGA: nie czekamy w zadaniu na walidację nowego zasobu (DGA ponawia zadanie i dlatego
potrzebuje cache, żeby przy ponowieniu nie tworzyć zasobu drugi raz). Nowy zasób przechodzi zwykłą
walidację portalu (sygnał post_save pliku), a wskazanie w AggregatedAEDInfo zmieniamy od razu.
"""

import logging

from mcod.core.tasks import extended_shared_task
from mcod.resources.aed_utils import (
    clean_up_main_aed,
    create_main_aed_file,
    create_main_aed_resource_with_dataset,
    update_aggregated_aed_info,
)

logger = logging.getLogger("mcod")


@extended_shared_task(
    atomic=False,
    name="mcod.resources.tasks.create_main_aed_resource_task",
)
def create_main_aed_resource_task() -> None:
    """1. Plik CSV wykazu z zasobów z flagą AED. 2. Zasób (i zbiór, jeśli trzeba).
    3. Wskazanie nowego zasobu w AggregatedAEDInfo i usunięcie poprzedniego. Po błędzie – sprzątanie."""
    from django.apps import apps

    Resource = apps.get_model("resources", "Resource")
    file_path = resource_pk = dataset_pk = None
    try:
        logger.info("Wykaz AED 1/3: plik CSV.")
        file_path = create_main_aed_file()
        logger.info("Wykaz AED 2/3: zasób.")
        resource_pk, dataset_pk = create_main_aed_resource_with_dataset(file_path)
        logger.info("Wykaz AED 3/3: AggregatedAEDInfo.")
        update_aggregated_aed_info(Resource.objects.get(pk=resource_pk))
        logger.info("Wykaz zbiorczy AED gotowy: zasób %s.", resource_pk)
        clean_up_main_aed(None, None, file_path)
    except Exception as exc:
        logger.error("Wykaz AED przerwany: %s – sprzątam.", exc)
        clean_up_main_aed(resource_pk, dataset_pk, file_path)
        raise
