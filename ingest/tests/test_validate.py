"""Testy walidatora względem schematu v0.2 (bez sieci)."""

import unittest

from ingest import validate
from ingest.fields import empty_record, load_schema


def record(**kw) -> dict:
    rec = empty_record()
    rec.update(
        id_aed="a", id_zrodlowe="1", szerokosc_geo="49.7", dlugosc_geo="21.7", nazwa_obiektu="Hala",
        dostep="publiczny", godziny_dostepnosci="nieznane", dostepny_24h="nieznane", status="aktywny",
        dysponent_nazwa="UM", dysponent_regon="140000017", data_weryfikacji="2026-11-01",
        zrodlo="danegovpl-krosno", licencja="CC0-1.0", data_aktualizacji="2026-11-21T12:00:00Z",
    )
    rec.update(kw)
    return rec


def problems(rec: dict, field: str) -> list[dict]:
    return [p for p in validate.validate([rec])["problemy"] if p["pole"] == field]


@unittest.skipIf(load_schema() is None, "brak schema/aed.schema.json")
class TestSchematV02(unittest.TestCase):
    def test_dostep_nieznany_to_ostrzezenie(self):
        found = problems(record(dostep="nieznany"), "dostep")
        self.assertEqual([p["poziom"] for p in found], ["ostrzezenie"])

    def test_pusty_dostep_dalej_blad(self):
        self.assertEqual([p["poziom"] for p in problems(record(dostep=""), "dostep")], ["blad"])

    def test_dystrybutor_bez_instytucji(self):
        found = problems(record(metoda_weryfikacji="dystrybutor"), "lokalizacje_potwierdzil")
        self.assertEqual([p["poziom"] for p in found], ["ostrzezenie"])
        ok = record(metoda_weryfikacji="dystrybutor", lokalizacje_potwierdzil="Centrum Ratownictwa X")
        self.assertEqual(problems(ok, "lokalizacje_potwierdzil"), [])
        self.assertEqual(problems(ok, "metoda_weryfikacji"), [])  # dystrybutor jest w słowniku v0.2

    def test_import_bez_instytucji_bez_ostrzezenia(self):
        self.assertEqual(problems(record(metoda_weryfikacji="import"), "lokalizacje_potwierdzil"), [])


if __name__ == "__main__":
    unittest.main()
