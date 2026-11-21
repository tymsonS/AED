"""Czytanie CSV zapisanych w Excelu (lista dystrybutora, plik gminy do pakietu dostawcy).

Polski Excel zapisuje CSV zwykle w Windows-1250 ze średnikiem, a daty jako DD.MM.RRRR
i liczby z przecinkiem dziesiętnym. Tu jest jedna obsługa tych wariantów dla całego ingest/.
"""

from __future__ import annotations

import csv
import io
from datetime import date, datetime
from pathlib import Path


def read_rows(path: Path) -> list[dict]:
    """Wiersze CSV: UTF-8 (z BOM lub bez) albo Windows-1250, separator przecinek albo średnik.
    Wartości przycięte, puste komórki jako „”."""
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1250")
    header = text.split("\n", 1)[0]
    delimiter = ";" if header.count(";") > header.count(",") else ","
    return [{k.strip(): (v or "").strip() for k, v in r.items() if k}
            for r in csv.DictReader(io.StringIO(text), delimiter=delimiter)]


def parse_date(text: str) -> date | None:
    """RRRR-MM-DD albo DD.MM.RRRR / DD.MM.RR (tak zapisuje polski Excel)."""
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d.%m.%y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    return None


def excel_values(rec: dict, fields: list[dict]) -> dict:
    """Wartości po Excelu na zapis schematu: daty DD.MM.RRRR -> RRRR-MM-DD, „49,75” -> „49.75”.
    Wartość, której nie da się rozpoznać, zostaje bez zmian – opisze ją walidator."""
    out = dict(rec)
    for f in fields:
        value = out.get(f["name"], "")
        if not value:
            continue
        if f["type"] == "date" and (parsed := parse_date(value)) is not None:
            out[f["name"]] = parsed.isoformat()
        elif f["type"] == "number" and value.count(",") == 1 and "." not in value:
            out[f["name"]] = value.replace(",", ".")
    return out
