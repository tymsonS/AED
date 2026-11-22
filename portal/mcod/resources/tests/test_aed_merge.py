"""Testy scalania wykazu zbiorczego AED (aed_merge.py) – bez bazy danych i bez Django."""

import json
from pathlib import Path

from mcod.resources import aed_merge as m


def row(**kw):
    base = {"nazwa_obiektu": "Szkoła", "szerokosc_geo": "49.70", "dlugosc_geo": "21.77"}
    base.update(kw)
    return base


def test_columns_follow_schema_v02():
    assert len(m.AED_COLUMNS) == 41
    assert m.AED_COLUMNS[0] == "id_aed" and m.AED_COLUMNS[-1] == "data_aktualizacji"
    assert "lokalizacje_potwierdzil" in m.AED_COLUMNS and "odpowiedzialny_za_stan_techniczny" in m.AED_COLUMNS
    assert m.MAIN_AED_COLUMNS[-3:] == ["instytucja_publikujaca", "id_zasobu_zrodlowego", "mozliwy_duplikat"]


def test_missing_required_columns():
    assert m.missing_required_columns(["szerokosc_geo", "nazwa_obiektu"]) == ["dlugosc_geo"]
    assert m.missing_required_columns(m.AED_COLUMNS) == []


def test_parse_coordinate():
    assert m.parse_coordinate("49,75") == 49.75
    assert m.parse_coordinate(" 21.5 ") == 21.5
    assert m.parse_coordinate("nan") is None
    assert m.parse_coordinate("abc") is None
    assert m.parse_coordinate(None) is None


def test_invalid_rows_skipped_one_by_one():
    rows = [row(), row(szerokosc_geo=""), row(szerokosc_geo="10", dlugosc_geo="10"), row(nazwa_obiektu="")]
    merged, skipped = m.merge_sources([("UM Krosna", 2838, 7, rows)])
    assert len(merged) == 1
    assert [s["powod"] for s in skipped] == ["brak poprawnych współrzędnych", "współrzędne poza Polską",
                                             "brak nazwy obiektu"]
    assert [s["wiersz"] for s in skipped] == [2, 3, 4]


def test_institution_and_system_id():
    merged, _ = m.merge_sources([("UM Krosna", 2838, 7, [row(id_zrodlowe="17")])])
    rec = merged[0]
    assert rec["instytucja_publikujaca"] == "UM Krosna" and rec["id_zasobu_zrodlowego"] == "7"
    assert rec["id_aed"] == m.stable_aed_id("2838", "17")  # z instytucji, nie z zasobu
    assert rec["szerokosc_geo"] == "49.700000"


def test_same_id_merged_newer_wins():
    old = row(id_aed="a", data_weryfikacji="2025-01-01", nazwa_obiektu="Stara nazwa")
    new = row(id_aed="a", data_weryfikacji="2026-11-20", nazwa_obiektu="Nowa nazwa")
    merged, _ = m.merge_sources([("Gmina", 1, 1, [old]), ("Szpital", 2, 2, [new])])
    assert len(merged) == 1 and merged[0]["nazwa_obiektu"] == "Nowa nazwa"


def test_tie_prefers_confirmed_location():
    a = row(id_aed="a", data_weryfikacji="2026-11-20")
    b = row(id_aed="a", data_weryfikacji="2026-11-20", lokalizacje_potwierdzil="Centrum Ratownictwa X")
    for order in ([a, b], [b, a]):
        merged, _ = m.merge_sources([("Gmina", 1, 1, order)])
        assert merged[0]["lokalizacje_potwierdzil"] == "Centrum Ratownictwa X"


def test_possible_duplicate_between_institutions_flagged_not_removed():
    gmina = row(id_aed="g", szerokosc_geo="49.700000", dlugosc_geo="21.770000")
    szpital = row(id_aed="s", szerokosc_geo="49.700200", dlugosc_geo="21.770000")  # ok. 22 m
    daleko = row(id_aed="d", szerokosc_geo="49.710000", dlugosc_geo="21.770000")   # ok. 1,1 km
    sam = row(id_aed="g2", szerokosc_geo="49.700100", dlugosc_geo="21.770000")     # ta sama instytucja
    merged, _ = m.merge_sources([("Gmina", 1, 1, [gmina, sam]), ("Szpital", 2, 2, [szpital, daleko])])
    by_id = {r["id_aed"]: r for r in merged}
    assert len(merged) == 4
    assert by_id["g"]["mozliwy_duplikat"] == "s"
    assert by_id["s"]["mozliwy_duplikat"] == "g;g2"
    assert by_id["d"]["mozliwy_duplikat"] == ""
    assert by_id["g2"]["mozliwy_duplikat"] == "s"


def test_two_aed_same_place_without_source_id_both_kept():
    # Dwa wejścia budynku: te same współrzędne, bez id_zrodlowe – oba zostają (review #58).
    merged, skipped = m.merge_sources([("Gmina", 1, 7, [row(), row()])])
    assert len(merged) == 2 and skipped == []
    assert merged[0]["id_aed"] != merged[1]["id_aed"]


def test_id_stable_when_institution_reuploads_file():
    # Ten sam plik gminy w zasobie nr 10 i (po ponownym wgraniu) nr 11 – te same id_aed (review #58).
    rows = [row(), row(), row(id_zrodlowe="17")]
    first, _ = m.merge_sources([("Gmina", 1, 10, [dict(r) for r in rows])])
    second, _ = m.merge_sources([("Gmina", 1, 11, [dict(r) for r in rows])])
    assert sorted(r["id_aed"] for r in first) == sorted(r["id_aed"] for r in second)


def test_same_aed_in_two_resources_of_institution_merged():
    merged, _ = m.merge_sources([("Gmina", 1, 10, [row()]), ("Gmina", 1, 11, [row()])])
    assert len(merged) == 1


def test_string_columns_match_aed_schema():
    # Schemat AEDane jest w repozytorium obok portal/ – lista kolumn tekstowych musi się z nim zgadzać.
    path = Path(__file__).resolve().parents[4] / "schema" / "aed.schema.json"
    if not path.exists():
        return
    fields = json.loads(path.read_text(encoding="utf-8"))["fields"]
    assert [f["name"] for f in fields] == m.AED_COLUMNS
    expected = [f["name"] for f in fields if f["type"] == "string"] + m.MAIN_AED_EXTRA_COLUMNS
    assert m.AED_STRING_COLUMNS == expected


def test_guessed_number_types_replaced_with_string():
    guessed = {"fields": [{"name": "kod_teryt_gminy", "type": "integer", "format": "default"},
                          {"name": "szerokosc_geo", "type": "number", "format": "default"},
                          {"name": "inna", "type": "integer", "format": "default"}],
               "missingValues": [""]}
    fixed = m.apply_aed_column_types(guessed)
    assert [f["type"] for f in fixed["fields"]] == ["string", "number", "integer"]
    assert fixed["missingValues"] == [""]
    assert guessed["fields"][0]["type"] == "integer"  # bez zmiany wejścia


def test_main_aed_table_detected_by_columns():
    assert m.is_main_aed_table(m.MAIN_AED_COLUMNS)
    assert not m.is_main_aed_table(m.AED_COLUMNS)
