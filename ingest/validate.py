"""Walidacja rekordów względem schema/aed.schema.json.

Sprawdza ograniczenia ze schematu (wymagane, słowniki, wzorce, zakresy) i część
reguł biznesowych z schema/README.md. Pełną walidację biblioteką frictionless
dodamy, gdy zależności trafią do repo osobnym PR-em.
"""

from __future__ import annotations

import re
from collections import Counter

from .fields import load_schema


def validate(records: list[dict]) -> dict:
    schema = load_schema()
    if schema is None:
        raise RuntimeError("Brak schema/aed.schema.json – walidacja wymaga schematu z obszaru schema/.")

    fields = schema["fields"]
    problems: list[dict] = []
    for idx, rec in enumerate(records):
        for f in fields:
            msg = _check_field(f, str(rec.get(f["name"], "") or ""))
            if msg:
                problems.append(_problem(idx, rec, f["name"], msg, "blad"))
        problems.extend(_business_rules(idx, rec))
        for note in rec.get("_uwagi", []):
            problems.append(_problem(idx, rec, "", note, "ostrzezenie"))

    dupes = Counter((r.get("zrodlo"), r.get("id_zrodlowe")) for r in records)
    for idx, rec in enumerate(records):
        if dupes[(rec.get("zrodlo"), rec.get("id_zrodlowe"))] > 1:
            problems.append(_problem(idx, rec, "id_zrodlowe", "powtórzone w obrębie źródła", "blad"))

    errors = sum(p["poziom"] == "blad" for p in problems)
    by_field = Counter(p["pole"] for p in problems if p["pole"])
    return {
        "rekordy": len(records),
        "rekordy_z_bledami": len({p["rekord"] for p in problems if p["poziom"] == "blad"}),
        "bledy": errors,
        "ostrzezenia": len(problems) - errors,
        "problemy_wg_pola": dict(by_field.most_common()),
        "problemy": problems,
    }


def _check_field(field: dict, value: str) -> str:
    c = field.get("constraints", {})
    if not value:
        return "pole wymagane jest puste" if c.get("required") else ""
    if "enum" in c and value not in c["enum"]:
        return f"wartość spoza słownika {c['enum']}"
    if "pattern" in c and not re.fullmatch(c["pattern"], value):
        return "niezgodny format"
    if field["type"] == "number":
        try:
            num = float(value)
        except ValueError:
            return "to nie jest liczba"
        if "minimum" in c and num < c["minimum"] or "maximum" in c and num > c["maximum"]:
            return "poza zakresem dla Polski"
    return ""


def _business_rules(idx: int, rec: dict) -> list[dict]:
    out = []
    hours, h24 = rec.get("godziny_dostepnosci", ""), rec.get("dostepny_24h", "")
    expected = "tak" if hours == "24/7" else "nieznane" if hours == "nieznane" else "nie"
    if hours and h24 and h24 != expected:
        out.append(_problem(idx, rec, "dostepny_24h", f"niespójne z godzinami (oczekiwano {expected})", "blad"))
    if not rec.get("dysponent_regon") and not rec.get("dysponent_nip"):
        out.append(_problem(idx, rec, "dysponent_regon", "brak REGON i NIP dysponenta", "ostrzezenie"))
    return out


def _problem(idx: int, rec: dict, field: str, msg: str, level: str) -> dict:
    return {
        "rekord": idx,
        "zrodlo": rec.get("zrodlo", ""),
        "id_zrodlowe": rec.get("id_zrodlowe", ""),
        "pole": field,
        "poziom": level,
        "komunikat": msg,
    }
