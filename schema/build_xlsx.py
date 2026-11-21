"""Generuje wzorcowy plik XLSX z schema/aed.schema.json.

Uruchomienie (z katalogu głównego repo):
    python schema/build_xlsx.py

Wynik: schema/wzorcowy-zakres-danych-aed.xlsx z arkuszami:
    Dane      – pusty szablon dla dysponenta: nagłówki + listy rozwijane i reguły walidacji;
                kolumny z „x-nadaje-system” (id_aed) są oznaczone i blokują wpisywanie
    Słownik   – opis każdego pola: typ, poziom, dozwolone wartości, przykład
    Przykład  – 3 poprawne (fikcyjne) rekordy z schema/przyklad-aed.csv

Nie edytuj XLSX ręcznie – zmieniaj aed.schema.json i uruchom skrypt ponownie.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
from pathlib import Path

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

SCHEMA_DIR = Path(__file__).resolve().parent
SCHEMA_PATH = SCHEMA_DIR / "aed.schema.json"
EXAMPLE_PATH = SCHEMA_DIR / "przyklad-aed.csv"
OUTPUT_PATH = SCHEMA_DIR / "wzorcowy-zakres-danych-aed.xlsx"

# Liczba wierszy szablonu, na które nakładamy listy rozwijane i reguły walidacji.
TEMPLATE_ROWS = 1000

# Kolory nagłówków wg poziomu. Kontrast tekstu do tła ≥ 4,5:1 (WCAG 2.2 AA);
# poziom jest też podany słownie w komentarzu i w arkuszu „Słownik”, więc kolor
# nie jest jedynym nośnikiem informacji.
LEVEL_STYLES = {
    "wymagane": ("8B1A1A", "FFFFFF"),
    "zalecane": ("FCE8B2", "000000"),
    "opcjonalne": ("E7E6E6", "000000"),
}

# Nagłówek kolumny, którą nadaje system (dysponent zostawia ją pustą). Kontrast ≥ 4,5:1.
SYSTEM_STYLE = ("D9E2F3", "1F3864")
SYSTEM_NOTE = "Nadaje system przy scalaniu – w pliku od dysponenta zostaw puste."

TYPE_LABELS = {
    "string": "tekst",
    "number": "liczba",
    "integer": "liczba całkowita",
    "boolean": "tak / nie",
    "date": "data (RRRR-MM-DD)",
    "datetime": "data i czas ISO 8601",
}


def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def allowed_values(field: dict) -> list[str] | None:
    """Zwraca listę dozwolonych wartości pola albo None, gdy wartości są dowolne."""
    if field["type"] == "boolean":
        return field.get("trueValues", ["tak"]) + field.get("falseValues", ["nie"])
    return field.get("constraints", {}).get("enum")


def format_hint(field: dict) -> str:
    """Krótki opis formatu: wzorzec, zakres liczbowy lub format specjalny."""
    constraints = field.get("constraints", {})
    parts = []
    if field.get("format") == "uuid":
        parts.append("UUID")
    if field.get("format") == "uri":
        parts.append("adres URL")
    if "pattern" in constraints:
        parts.append(f"wzorzec: {constraints['pattern']}")
    if "minimum" in constraints or "maximum" in constraints:
        parts.append(f"zakres: {constraints.get('minimum', '')}–{constraints.get('maximum', '')}")
    return "; ".join(parts)


def is_system_field(field: dict) -> bool:
    """Pole nadawane przez ingest/ – wymagane w zbiorze wynikowym, puste w pliku dysponenta."""
    return bool(field.get("x-nadaje-system"))


def level_label(field: dict) -> str:
    if is_system_field(field):
        return f"{field['x-poziom']} w zbiorze wynikowym; nadaje system"
    return field["x-poziom"]


def style_header(cell, level: str, system: bool = False) -> None:
    fill, font = SYSTEM_STYLE if system else LEVEL_STYLES[level]
    cell.fill = PatternFill("solid", fgColor=fill)
    cell.font = Font(bold=True, italic=system, color=font)
    cell.alignment = Alignment(vertical="center")


def add_validations(ws, fields: list[dict]) -> None:
    """Listy rozwijane i reguły walidacji w arkuszu „Dane”."""
    for idx, field in enumerate(fields, start=1):
        col = get_column_letter(idx)
        cell_range = f"{col}2:{col}{TEMPLATE_ROWS + 1}"
        constraints = field.get("constraints", {})
        values = allowed_values(field)
        dv = None
        if is_system_field(field):
            # Długość tekstu = 0: Excel/LibreOffice odrzuci każdą wpisaną wartość.
            dv = DataValidation(type="textLength", operator="equal", formula1="0", allow_blank=True)
            dv.error = SYSTEM_NOTE
        elif values:
            dv = DataValidation(type="list", formula1='"' + ",".join(values) + '"', allow_blank=True)
            dv.error = "Wybierz wartość z listy: " + ", ".join(values)
        elif field["type"] == "number" and ("minimum" in constraints or "maximum" in constraints):
            dv = DataValidation(
                type="decimal",
                operator="between",
                formula1=str(constraints["minimum"]),
                formula2=str(constraints["maximum"]),
                allow_blank=True,
            )
            dv.error = f"Wartość musi być w zakresie {constraints['minimum']}–{constraints['maximum']}."
        elif field["type"] == "integer":
            dv = DataValidation(type="whole", operator="between", formula1="-10", formula2="200", allow_blank=True)
            dv.error = "Podaj liczbę całkowitą."
        if dv is None:
            continue
        dv.errorTitle = field.get("title", field["name"])
        dv.showErrorMessage = True
        ws.add_data_validation(dv)
        dv.add(cell_range)


def build_data_sheet(ws, fields: list[dict]) -> None:
    ws.title = "Dane"
    for idx, field in enumerate(fields, start=1):
        cell = ws.cell(row=1, column=idx, value=field["name"])
        style_header(cell, field["x-poziom"], is_system_field(field))
        note = f"{field.get('title', field['name'])}\nPoziom: {level_label(field)}\nTyp: {TYPE_LABELS[field['type']]}"
        if is_system_field(field):
            note = f"{SYSTEM_NOTE}\n\n{note}"
        if field.get("description"):
            note += f"\n\n{field['description']}"
        cell.comment = Comment(note, "Misja AED", width=320, height=180)
        ws.column_dimensions[get_column_letter(idx)].width = max(14, len(field["name"]) + 4)
        # Kolumny tekstowe jako tekst, żeby Excel nie zmieniał np. kodów TERYT, NIP czy telefonów.
        if field["type"] in ("string", "date", "datetime"):
            for row in range(2, TEMPLATE_ROWS + 2):
                ws.cell(row=row, column=idx).number_format = "@"
    ws.freeze_panes = "A2"
    add_validations(ws, fields)


def build_dictionary_sheet(ws, fields: list[dict], schema: dict) -> None:
    headers = ["Pole", "Nazwa", "Grupa", "Poziom", "Typ", "Format", "Dozwolone wartości", "Opis", "Przykład"]
    ws.append([f"{schema['title']} – wersja {schema.get('x-wersja', '')} ({schema.get('x-data-wersji', '')})"])
    ws["A1"].font = Font(bold=True, size=13)
    ws.append(
        [
            "Poziomy: wymagane – bez nich rekord jest odrzucany; zalecane – brak daje ostrzeżenie; "
            "opcjonalne – można pominąć. Pola „nadaje system” (id_aed) dysponent zostawia puste – "
            "uzupełnia je system przy scalaniu. Kodowanie CSV: UTF-8, separator przecinek."
        ]
    )
    ws.append([])
    ws.append(headers)
    for cell in ws[4]:
        cell.font = Font(bold=True)
    for field in fields:
        values = allowed_values(field)
        ws.append(
            [
                field["name"],
                field.get("title", ""),
                field.get("x-grupa", ""),
                level_label(field),
                TYPE_LABELS[field["type"]],
                format_hint(field),
                ", ".join(values) if values else "",
                field.get("description", ""),
                field.get("x-przyklad", ""),
            ]
        )
    widths = [28, 30, 14, 22, 22, 34, 34, 70, 22]
    for idx, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(idx)].width = width
    for row in ws.iter_rows(min_row=5):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "A5"


def build_example_sheet(ws, fields: list[dict]) -> None:
    for idx, field in enumerate(fields, start=1):
        cell = ws.cell(row=1, column=idx, value=field["name"])
        style_header(cell, field["x-poziom"], is_system_field(field))
        ws.column_dimensions[get_column_letter(idx)].width = max(14, len(field["name"]) + 4)
    with EXAMPLE_PATH.open(encoding="utf-8", newline="") as f:
        for row_idx, record in enumerate(csv.DictReader(f), start=2):
            for col_idx, field in enumerate(fields, start=1):
                cell = ws.cell(row=row_idx, column=col_idx, value=record[field["name"]])
                cell.number_format = "@"
    ws.freeze_panes = "A2"


def build() -> Path:
    schema = load_schema()
    fields = schema["fields"]
    wb = Workbook()
    build_data_sheet(wb.active, fields)
    build_dictionary_sheet(wb.create_sheet("Słownik"), fields, schema)
    build_example_sheet(wb.create_sheet("Przykład"), fields)
    wb.properties.title = schema["title"]
    wb.properties.creator = "Misja AED – HackNation 2026"
    # Data wersji schematu w metadanych zamiast bieżącej daty (sam plik i tak różni się
    # bajtowo przy każdym generowaniu, bo ZIP zapisuje znaczniki czasu).
    fixed = dt.datetime.fromisoformat(schema.get("x-data-wersji", "2026-11-21"))
    wb.properties.created = fixed
    wb.properties.modified = fixed
    wb.save(OUTPUT_PATH)
    return OUTPUT_PATH


if __name__ == "__main__":
    print(f"Zapisano {build()}")
