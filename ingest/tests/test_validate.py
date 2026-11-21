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


@unittest.skipIf(load_schema() is None, "brak schema/aed.schema.json")
class TestTypyPol(unittest.TestCase):
    """Review #31: walidator nie sprawdzał typów, więc w_budynku = true/false przeszło niezauważone."""

    def assert_errors(self, field, bad, good):
        for value in bad:
            found = problems(record(**{field: value}), field)
            self.assertEqual([p["poziom"] for p in found], ["blad"], f"{field}={value!r}")
        for value in good:
            self.assertEqual(problems(record(**{field: value}), field), [], f"{field}={value!r}")

    def test_boolean_tak_nie(self):
        self.assert_errors("w_budynku", ["true", "false", "1", "TAK"], ["tak", "nie", ""])

    def test_integer(self):
        self.assert_errors("kondygnacja", ["0.5", "1;2", "parter"], ["0", "-1", "12", ""])

    def test_date(self):
        self.assert_errors("data_przegladu", ["2026-13-01", "2026-02-30", "21.11.2026", "2026-11"],
                           ["2026-11-21", ""])
        self.assert_errors("data_weryfikacji", ["2026/11/01"], ["2026-11-01"])

    def test_datetime(self):
        self.assert_errors("data_aktualizacji", ["2026-11-21 12:00", "2026-11-21T12:00:00", "2026-11-21"],
                           ["2026-11-21T12:00:00Z", "2026-11-21T12:00:00+01:00", "2026-11-21T12:00Z"])

    def test_uuid(self):
        self.assert_errors("id_aed", ["a", "BCB0AEF5-997B-5080-BEFB-9BBF054CAFE5", "bcb0aef5997b5080befb9bbf054cafe5"],
                           ["bcb0aef5-997b-5080-befb-9bbf054cafe5"])

    def test_uri(self):
        self.assert_errors("zdjecie_url", ["ftp://x.pl/a.jpg", "zdjecie.jpg", "https://"],
                           ["https://example.pl/a.jpg", "http://x.pl", ""])

    def test_unikalne_id_aed(self):
        a = record(id_aed="bcb0aef5-997b-5080-befb-9bbf054cafe5", id_zrodlowe="1")
        b = record(id_aed="bcb0aef5-997b-5080-befb-9bbf054cafe5", id_zrodlowe="2")
        found = [p for p in validate.validate([a, b])["problemy"] if p["pole"] == "id_aed"]
        self.assertEqual(len(found), 2)
        self.assertTrue(all("unikalna" in p["komunikat"] for p in found))


if __name__ == "__main__":
    unittest.main()
