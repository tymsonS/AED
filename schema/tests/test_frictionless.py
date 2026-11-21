"""Pełna walidacja biblioteką frictionless (v5).

Uruchomienie:
    pip install "frictionless>=5,<6" openpyxl pytest
    python -m pytest schema/tests -v

Brak biblioteki frictionless albo pliku XLSX to błąd testu, nie pominięcie (skip) —
wszystkie testy muszą przechodzić.
Sprawdzają: (1) czy aed.schema.json jest poprawnym Table Schema,
(2) czy przyklad-aed.csv przechodzi walidację względem schematu,
(3) czy arkusz „Przykład” w wygenerowanym XLSX przechodzi walidację.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import frictionless

SCHEMA_DIR = Path(__file__).resolve().parents[1]


def _load_schema() -> "frictionless.Schema":
    # Schemat ładujemy ze słownika, a nie ze ścieżki: frictionless v5 zapamiętuje ścieżkę
    # bezwzględną deskryptora i przy Resource(basepath=...) odrzuca ją jako „not safe”.
    descriptor = json.loads((SCHEMA_DIR / "aed.schema.json").read_text(encoding="utf-8"))
    return frictionless.Schema.from_descriptor(descriptor)


def _errors(report) -> list:
    return report.flatten(["rowNumber", "fieldName", "type", "note"])


def test_schema_descriptor_is_valid():
    descriptor = json.loads((SCHEMA_DIR / "aed.schema.json").read_text(encoding="utf-8"))
    report = frictionless.Schema.validate_descriptor(descriptor)
    assert report.valid, [error.message for error in report.errors]
    # Dodatkowo: wczytanie deskryptora rzuca FrictionlessException, gdy jest niepoprawny.
    frictionless.Schema.from_descriptor(descriptor)


def test_example_csv_passes_schema():
    schema = _load_schema()
    resource = frictionless.Resource(path="przyklad-aed.csv", basepath=str(SCHEMA_DIR), schema=schema)
    report = resource.validate()
    assert report.valid, _errors(report)


def test_example_xlsx_sheet_passes_schema():
    xlsx = SCHEMA_DIR / "wzorcowy-zakres-danych-aed.xlsx"
    assert xlsx.exists(), "Brak XLSX – uruchom: python schema/build_xlsx.py"
    schema = _load_schema()
    resource = frictionless.Resource(
        path=xlsx.name,
        basepath=str(SCHEMA_DIR),
        schema=schema,
        dialect=frictionless.Dialect(controls=[frictionless.formats.ExcelControl(sheet="Przykład")]),
    )
    report = resource.validate()
    assert report.valid, _errors(report)


# --- Plik od dysponenta: id_aed puste (nadaje system) ---------------------------


def _dispatcher_schema() -> "frictionless.Schema":
    """Schemat pliku od dysponenta wg schema/README.md: bez primaryKey i bez
    `required` w polach z x-nadaje-system."""
    descriptor = json.loads((SCHEMA_DIR / "aed.schema.json").read_text(encoding="utf-8"))
    descriptor.pop("primaryKey", None)
    for field in descriptor["fields"]:
        if field.get("x-nadaje-system"):
            field["constraints"].pop("required", None)
    return frictionless.Schema.from_descriptor(descriptor)


def _example_rows(blank_system_fields: bool) -> list[dict]:
    with (SCHEMA_DIR / "przyklad-aed.csv").open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if blank_system_fields:
        descriptor = json.loads((SCHEMA_DIR / "aed.schema.json").read_text(encoding="utf-8"))
        system = [fd["name"] for fd in descriptor["fields"] if fd.get("x-nadaje-system")]
        for row in rows:
            for name in system:
                row[name] = ""
    return rows


def _write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_dispatcher_file_without_id_aed_passes_dispatcher_schema(tmp_path):
    _write_csv(tmp_path / "dysponent.csv", _example_rows(blank_system_fields=True))
    resource = frictionless.Resource(path="dysponent.csv", basepath=str(tmp_path), schema=_dispatcher_schema())
    report = resource.validate()
    assert report.valid, _errors(report)


def test_output_dataset_without_id_aed_is_rejected(tmp_path):
    # Zbiór wynikowy bez id_aed musi być odrzucony – tam pole jest wymagane.
    _write_csv(tmp_path / "wynik.csv", _example_rows(blank_system_fields=True))
    resource = frictionless.Resource(path="wynik.csv", basepath=str(tmp_path), schema=_load_schema())
    report = resource.validate()
    assert not report.valid
    # Jedyne błędy: brak wymaganego id_aed i pusty klucz główny – nic innego.
    kinds = {(row[1], row[2]) for row in _errors(report)}
    assert kinds == {("id_aed", "constraint-error"), (None, "primary-key")}, _errors(report)


def test_xlsx_data_sheet_blocks_input_in_system_fields():
    from openpyxl import load_workbook

    ws = load_workbook(SCHEMA_DIR / "wzorcowy-zakres-danych-aed.xlsx")["Dane"]
    header = [cell.value for cell in ws[1]]
    col = header.index("id_aed") + 1
    letter = ws.cell(row=1, column=col).column_letter
    assert "zostaw puste" in ws.cell(row=1, column=col).comment.text
    rules = [
        dv
        for dv in ws.data_validations.dataValidation
        if str(dv.sqref).startswith(f"{letter}2:")
    ]
    assert len(rules) == 1
    assert (rules[0].type, rules[0].operator, rules[0].formula1) == ("textLength", "equal", "0")
