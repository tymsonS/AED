"""Testy spójności schematu AED i przykładowych rekordów.

Uruchomienie: python -m pytest schema/tests
Bez sieci – sprawdzamy ograniczenia Table Schema lekkim walidatorem oraz reguły
biznesowe opisane w schema/README.md. Pełną walidację biblioteką frictionless
robi tests/test_frictionless.py.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import re
import uuid
from pathlib import Path

import pytest

SCHEMA_DIR = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((SCHEMA_DIR / "aed.schema.json").read_text(encoding="utf-8"))
FIELDS = {f["name"]: f for f in SCHEMA["fields"]}
LEVELS = {"wymagane", "zalecane", "opcjonalne"}
TYPES = {"string", "number", "integer", "boolean", "date", "datetime"}

with (SCHEMA_DIR / "przyklad-aed.csv").open(encoding="utf-8", newline="") as _f:
    _reader = csv.DictReader(_f)
    EXAMPLE_HEADER = _reader.fieldnames
    EXAMPLES = list(_reader)


# --- Pomocnicze: sumy kontrolne -------------------------------------------------


def nip_is_valid(value: str) -> bool:
    weights = [6, 5, 7, 2, 3, 4, 5, 6, 7]
    check = sum(int(d) * w for d, w in zip(value[:9], weights)) % 11
    return check != 10 and check == int(value[9])


def regon_is_valid(value: str) -> bool:
    if len(value) == 9:
        weights = [8, 9, 2, 3, 4, 5, 6, 7]
    else:
        weights = [2, 4, 8, 5, 0, 9, 7, 3, 6, 1, 2, 4, 8]
    check = sum(int(d) * w for d, w in zip(value, weights)) % 11
    return (0 if check == 10 else check) == int(value[-1])


# --- Spójność samego schematu ---------------------------------------------------


def test_field_names_are_unique_snake_case_without_diacritics():
    names = [f["name"] for f in SCHEMA["fields"]]
    assert len(names) == len(set(names))
    for name in names:
        assert re.fullmatch(r"[a-z0-9_]+", name), name


@pytest.mark.parametrize("field", SCHEMA["fields"], ids=lambda f: f["name"])
def test_field_has_level_type_and_group(field):
    assert field["x-poziom"] in LEVELS
    assert field["type"] in TYPES
    assert field.get("x-grupa")
    assert field.get("title")


@pytest.mark.parametrize("field", SCHEMA["fields"], ids=lambda f: f["name"])
def test_required_constraint_matches_level(field):
    required = field.get("constraints", {}).get("required", False)
    assert required == (field["x-poziom"] == "wymagane")


def test_agents_md_mandatory_fields_present():
    # AGENTS.md: każdy rekord ma pole `zrodlo` i `data_aktualizacji`.
    for name in ("zrodlo", "data_aktualizacji"):
        assert FIELDS[name]["x-poziom"] == "wymagane"


def test_primary_key_is_a_field():
    for key in SCHEMA["primaryKey"]:
        assert key in FIELDS


def test_only_id_aed_is_assigned_by_system():
    # Plan techniczny + decyzja Krystiana: id_aed nadaje ingest/ przy scalaniu.
    system = [f["name"] for f in SCHEMA["fields"] if f.get("x-nadaje-system")]
    assert system == ["id_aed"]
    for name in system:
        # W zbiorze wynikowym pole pozostaje wymagane, unikalne i jest kluczem głównym.
        assert FIELDS[name]["constraints"] == {"required": True, "unique": True}
        assert name in SCHEMA["primaryKey"]


def test_no_field_stores_a_lock_code():
    # Kod do szafki nigdy nie trafia do otwartych danych – tylko informacja tak/nie.
    assert FIELDS["kod_do_szafki_u_dyspozytora"]["type"] == "boolean"


# --- Przykładowe rekordy wobec ograniczeń schematu ------------------------------


def test_example_header_matches_schema_order():
    assert EXAMPLE_HEADER == [f["name"] for f in SCHEMA["fields"]]


def test_examples_have_three_records():
    assert len(EXAMPLES) == 3


def check_value(field: dict, value: str) -> None:
    """Rzuca AssertionError, gdy niepusta wartość łamie typ lub ograniczenia pola."""
    constraints = field.get("constraints", {})
    kind = field["type"]
    if kind == "number":
        number = float(value)
        assert constraints.get("minimum", number) <= number <= constraints.get("maximum", number)
    elif kind == "integer":
        int(value)
    elif kind == "boolean":
        assert value in field["trueValues"] + field["falseValues"]
    elif kind == "date":
        dt.date.fromisoformat(value)
    elif kind == "datetime":
        # Czas polski bez strefy – dane tabelaryczne dane.gov.pl nie przyjmują Z ani ±HH:MM (#61).
        assert not re.search(r"(Z|[+-]\d{2}:?\d{2})$", value), "data i czas bez strefy czasowej"
        dt.datetime.fromisoformat(value)
    if field.get("format") == "uuid":
        uuid.UUID(value)
    if field.get("format") == "uri":
        assert re.match(r"https?://", value)
    if "enum" in constraints:
        assert value in constraints["enum"]
    if "pattern" in constraints:
        assert re.fullmatch(constraints["pattern"], value)


@pytest.mark.parametrize("record", EXAMPLES, ids=lambda r: r["id_zrodlowe"])
def test_example_record_satisfies_schema(record):
    for name, field in FIELDS.items():
        value = record[name]
        if value == "":
            assert not field.get("constraints", {}).get("required"), f"brak wymaganego pola {name}"
            continue
        try:
            check_value(field, value)
        except (AssertionError, ValueError) as exc:
            pytest.fail(f"{name}={value!r}: {exc}")


def test_example_ids_are_unique():
    ids = [r["id_aed"] for r in EXAMPLES]
    assert len(ids) == len(set(ids))


# --- Reguły biznesowe (schema/README.md) ----------------------------------------


@pytest.mark.parametrize("record", EXAMPLES, ids=lambda r: r["id_zrodlowe"])
def test_business_rules(record):
    hours = record["godziny_dostepnosci"]
    flag = record["dostepny_24h"]
    if hours == "nieznane":
        assert flag == "nieznane"
    elif hours == "24/7":
        assert flag == "tak"
    else:
        assert flag == "nie"
    if record["dysponent_nip"]:
        assert nip_is_valid(record["dysponent_nip"])
    if record["dysponent_regon"]:
        assert regon_is_valid(record["dysponent_regon"])
    assert record["dysponent_nip"] or record["dysponent_regon"], "podaj REGON lub NIP"


def test_nip_and_regon_checksums_detect_errors():
    assert nip_is_valid("5250000015")
    assert not nip_is_valid("5250000016")
    assert regon_is_valid("140000017")
    assert not regon_is_valid("140000018")


# --- Decyzje v0.2 (issue #25, ustalenia z mentorem pkt 4–6) -----------------------


def test_v02_dostep_allows_unknown():
    assert FIELDS["dostep"]["constraints"]["enum"] == ["publiczny", "ograniczony", "prywatny", "nieznany"]
    assert FIELDS["dostep"]["x-poziom"] == "wymagane"


def test_v02_verification_by_distributor():
    assert "dystrybutor" in FIELDS["metoda_weryfikacji"]["constraints"]["enum"]


def test_v02_responsibility_fields():
    # Lokalizacja: kto / kiedy / jak; stan techniczny: kto / kiedy.
    for name, group in (("lokalizacje_potwierdzil", "Weryfikacja"), ("odpowiedzialny_za_stan_techniczny", "Stan")):
        field = FIELDS[name]
        assert field["type"] == "string"
        assert field["x-grupa"] == group
        assert field["x-poziom"] == "zalecane"
        assert not field.get("constraints", {}).get("required")
    assert FIELDS["data_weryfikacji"]["x-poziom"] == "wymagane"
    assert FIELDS["data_przegladu"]["x-grupa"] == "Stan"
    # Bez drugiej daty o tym samym znaczeniu co data_weryfikacji.
    assert "data_potwierdzenia_lokalizacji" not in FIELDS


def test_v02_version_and_sources_registry():
    assert SCHEMA["x-wersja"] == "0.2.0"
    assert "sources.toml" in FIELDS["zrodlo"]["description"]
    assert "osm" not in FIELDS["zrodlo"]["description"].lower()


def test_v02_examples_use_new_values():
    by_id = {r["id_zrodlowe"]: r for r in EXAMPLES}
    assert by_id["KRK-UD-17"]["metoda_weryfikacji"] == "dystrybutor"
    assert by_id["KRK-UD-17"]["lokalizacje_potwierdzil"]
    assert by_id["KRK-UD-17"]["odpowiedzialny_za_stan_techniczny"]
    assert by_id["GDA-0042"]["dostep"] == "nieznany"
