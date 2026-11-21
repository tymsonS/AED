"""Pełna walidacja biblioteką frictionless (v5).

Uruchomienie:
    pip install "frictionless>=5,<6" openpyxl pytest
    python -m pytest schema/tests -v

Gdy frictionless nie jest zainstalowany, testy są pomijane (skip), a nie zaliczane.
Sprawdzają: (1) czy aed.schema.json jest poprawnym Table Schema,
(2) czy przyklad-aed.csv przechodzi walidację względem schematu,
(3) czy arkusz „Przykład” w wygenerowanym XLSX przechodzi walidację.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

frictionless = pytest.importorskip("frictionless")

SCHEMA_DIR = Path(__file__).resolve().parents[1]


def _errors(report) -> list:
    return report.flatten(["rowNumber", "fieldName", "type", "note"])


def test_schema_descriptor_is_valid():
    descriptor = json.loads((SCHEMA_DIR / "aed.schema.json").read_text(encoding="utf-8"))
    report = frictionless.Schema.validate_descriptor(descriptor)
    assert report.valid, [error.message for error in report.errors]
    # Dodatkowo: wczytanie deskryptora rzuca FrictionlessException, gdy jest niepoprawny.
    frictionless.Schema.from_descriptor(descriptor)


def test_example_csv_passes_schema():
    schema = frictionless.Schema.from_descriptor(str(SCHEMA_DIR / "aed.schema.json"))
    resource = frictionless.Resource(path="przyklad-aed.csv", basepath=str(SCHEMA_DIR), schema=schema)
    report = resource.validate()
    assert report.valid, _errors(report)


def test_example_xlsx_sheet_passes_schema():
    xlsx = SCHEMA_DIR / "wzorcowy-zakres-danych-aed.xlsx"
    if not xlsx.exists():
        pytest.skip("Brak XLSX – uruchom: python schema/build_xlsx.py")
    schema = frictionless.Schema.from_descriptor(str(SCHEMA_DIR / "aed.schema.json"))
    resource = frictionless.Resource(
        path=xlsx.name,
        basepath=str(SCHEMA_DIR),
        schema=schema,
        dialect=frictionless.Dialect(controls=[frictionless.formats.ExcelControl(sheet="Przykład")]),
    )
    report = resource.validate()
    assert report.valid, _errors(report)
