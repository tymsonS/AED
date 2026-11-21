"""Lista pól wzorcowego zakresu danych AED.

Źródłem prawdy jest schema/aed.schema.json (obszar schema/, właściciel: Krystian).
Gdy plik istnieje, kolejność i nazwy pól bierzemy z niego. Lista FALLBACK_FIELDS
służy tylko do pracy, zanim schemat trafi na main – test pilnuje, żeby była zgodna.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "schema" / "aed.schema.json"

FALLBACK_FIELDS: tuple[str, ...] = (
    "id_aed", "id_zrodlowe", "numer_seryjny",
    "szerokosc_geo", "dlugosc_geo",
    "wojewodztwo", "powiat", "gmina", "kod_teryt_gminy",
    "miejscowosc", "ulica", "numer_budynku", "kod_pocztowy",
    "nazwa_obiektu", "opis_lokalizacji", "kondygnacja", "w_budynku",
    "dostep", "godziny_dostepnosci", "dostepny_24h",
    "szafka_zamykana", "kod_do_szafki_u_dyspozytora",
    "producent", "model", "tryb_pediatryczny",
    "status", "data_przegladu", "data_waznosci_elektrod", "data_waznosci_baterii",
    "dysponent_nazwa", "dysponent_regon", "dysponent_nip", "telefon_kontaktowy",
    "data_weryfikacji", "metoda_weryfikacji", "zdjecie_url",
    "zrodlo", "licencja", "data_aktualizacji",
)


@lru_cache(maxsize=1)
def load_schema() -> dict | None:
    """Zwraca schemat Frictionless albo None, jeśli schema/ nie jest jeszcze na gałęzi."""
    if not SCHEMA_PATH.exists():
        return None
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def field_names() -> tuple[str, ...]:
    schema = load_schema()
    if schema is None:
        return FALLBACK_FIELDS
    return tuple(f["name"] for f in schema["fields"])


def empty_record() -> dict[str, str]:
    return {name: "" for name in field_names()}
