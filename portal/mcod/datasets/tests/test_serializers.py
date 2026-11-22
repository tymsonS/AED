from typing import Set

from django.utils.translation import override

from mcod.datasets.serializers import DatasetCSVSchema


def test_dataset_csv_schema_has_all_expected_headers():
    with override("pl"):
        headers: Set[str] = set(DatasetCSVSchema().get_csv_headers())

    expected_fields: Set[str] = {
        "id",
        "uuid",
        "nazwa",
        "opis",
        "url",
        "Częstotliwość aktualizacji",
        "Sposób udostępnienia",
        "Instytucja",
        "Kategoria",
        "Status",
        "Warunki ponownego użycia",
        "utworzony przez",
        "utworzony",
        "zmodyfikowany przez",
        "zmodyfikowany",
        "Liczba obserwujących",
        "Liczba oznaczeń zbioru jako ulubiony",
        "Zbiór zawiera dane o wysokiej wartości",
        "Zbiór zawiera dane o wysokiej wartości z wykazu KE",
        "Zbiór zawiera dane dynamiczne",
        "Zbiór zawiera dane badawcze",
    }

    missing = expected_fields - headers
    assert not missing, f"Serializer DatasetCSVSchema does not contain fields: {missing}"
