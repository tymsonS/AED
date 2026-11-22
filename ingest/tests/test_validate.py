"""Testy walidatora względem schematu v0.2 (bez sieci)."""

import unittest
from pathlib import Path

from ingest import validate
from ingest.fields import empty_record, load_schema


def record(**kw) -> dict:
    rec = empty_record()
    rec.update(
        id_aed="a", id_zrodlowe="1", szerokosc_geo="49.7", dlugosc_geo="21.7", nazwa_obiektu="Hala",
        dostep="publiczny", godziny_dostepnosci="nieznane", dostepny_24h="nieznane", status="aktywny",
        dysponent_nazwa="UM", dysponent_regon="140000017", data_weryfikacji="2026-11-01",
        zrodlo="danegovpl-krosno", licencja="CC0-1.0", data_aktualizacji="2026-11-21T13:00:00",
    )
    rec.update(kw)
    return rec


def problems(rec: dict, field: str) -> list[dict]:
    return [p for p in validate.validate([rec])["problemy"] if p["pole"] == field]


@unittest.skipIf(load_schema() is None, "brak schema/aed.schema.json")
class TestSchemaV02(unittest.TestCase):
    def test_unknown_access_is_warning(self):
        found = problems(record(dostep="nieznany"), "dostep")
        self.assertEqual([p["poziom"] for p in found], ["ostrzezenie"])

    def test_empty_access_is_error(self):
        self.assertEqual([p["poziom"] for p in problems(record(dostep=""), "dostep")], ["blad"])

    def test_distributor_without_confirming_institution(self):
        found = problems(record(metoda_weryfikacji="dystrybutor"), "lokalizacje_potwierdzil")
        self.assertEqual([p["poziom"] for p in found], ["ostrzezenie"])
        ok = record(metoda_weryfikacji="dystrybutor", lokalizacje_potwierdzil="Centrum Ratownictwa X")
        self.assertEqual(problems(ok, "lokalizacje_potwierdzil"), [])
        self.assertEqual(problems(ok, "metoda_weryfikacji"), [])  # dystrybutor jest w słowniku v0.2

    def test_import_without_institution_no_warning(self):
        self.assertEqual(problems(record(metoda_weryfikacji="import"), "lokalizacje_potwierdzil"), [])


@unittest.skipIf(load_schema() is None, "brak schema/aed.schema.json")
class TestFieldTypes(unittest.TestCase):
    """Review #31: walidator nie sprawdzał typów, więc w_budynku = true/false przeszło niezauważone."""

    def assert_errors(self, field, bad, good):
        for value in bad:
            found = problems(record(**{field: value}), field)
            self.assertEqual([p["poziom"] for p in found], ["blad"], f"{field}={value!r}")
        for value in good:
            self.assertEqual(problems(record(**{field: value}), field), [], f"{field}={value!r}")

    def test_boolean_tak_nie_only(self):
        self.assert_errors("w_budynku", ["true", "false", "1", "TAK"], ["tak", "nie", ""])

    def test_integer(self):
        self.assert_errors("kondygnacja", ["0.5", "1;2", "parter"], ["0", "-1", "12", "", " 3", "+2"])

    def test_date(self):
        self.assert_errors("data_przegladu", ["2026-13-01", "2026-02-30", "21.11.2026", "2026-11"],
                           ["2026-11-21", ""])
        self.assert_errors("data_weryfikacji", ["2026/11/01"], ["2026-11-01"])

    def test_datetime(self):
        # #61: czas polski bez strefy – portal dane.gov.pl nie przyjmuje daty ze strefą.
        # Review #38: bez sekund frictionless odrzuca, więc u nas też błąd.
        self.assert_errors("data_aktualizacji",
                           ["2026-11-21 12:00", "2026-11-21", "2026-11-21T12:00", "2026-11-21T12:00:00Z",
                            "2026-11-21T12:00:00+01:00", "2026-11-21T12:00:00.5"],
                           ["2026-11-21T13:00:00", "2026-11-21T13:00:00.123456"])

    def test_datetime_with_zone_says_portal_rejects_it(self):
        problems = validate.validate([record(data_aktualizacji="2026-11-21T12:00:00Z")])["problemy"]
        message = next(p["komunikat"] for p in problems if p["pole"] == "data_aktualizacji")
        self.assertIn("dane.gov.pl tego nie przyjmie", message)

    def test_number_must_be_finite(self):
        # Review #41: „nan” parsuje się jako float i przechodziło jako współrzędna.
        self.assert_errors("szerokosc_geo", ["nan", "NaN", "inf", "abc"], ["49.75", "54.9"])

    def test_uuid(self):
        self.assert_errors("id_aed", ["a", "BCB0AEF5-997B-5080-BEFB-9BBF054CAFE5", "bcb0aef5997b5080befb9bbf054cafe5"],
                           ["bcb0aef5-997b-5080-befb-9bbf054cafe5"])

    def test_uri(self):
        self.assert_errors("zdjecie_url", ["ftp://x.pl/a.jpg", "zdjecie.jpg", "https://", " https://x.pl",
                                           "https://x.pl ", "https://[broken", "https://@", "https://:80"],
                           ["https://example.pl/a.jpg", "http://x.pl", ""])

    def test_unique_id_aed(self):
        a = record(id_aed="bcb0aef5-997b-5080-befb-9bbf054cafe5", id_zrodlowe="1")
        b = record(id_aed="bcb0aef5-997b-5080-befb-9bbf054cafe5", id_zrodlowe="2")
        found = [p for p in validate.validate([a, b])["problemy"] if p["pole"] == "id_aed"]
        self.assertEqual(len(found), 2)
        self.assertTrue(all("unikalna" in p["komunikat"] for p in found))


# Celowo ostrzej niż frictionless – z powodem (README, „Typy pól”). Każda inna różnica to błąd
# walidatora, a wpis, który przestał być ostrzejszy, test zgłasza jako nieaktualny.
STRICTER_THAN_FRICTIONLESS = {
    # data_aktualizacji: tylko RRRR-MM-DDTHH:MM:SS[.SSSSSS] bez strefy – jedyne zapisy z T, które przyjmuje
    # portal dane.gov.pl (DATE_BASE_FORMATS, #61); strefa, ułamek innej długości albo spacja zamiast T: błąd
    ("data_aktualizacji", "2026-11-21T12:00:00Z"),
    ("data_aktualizacji", "2026-11-21T12:00:00+01:00"),
    ("data_aktualizacji", "2026-11-21T12:00:00.5Z"),
    ("data_aktualizacji", "2026-11-21T12:00:00-00:00"),
    ("data_aktualizacji", "2026-11-21T12:00:00+14:00"),
    ("data_aktualizacji", "2026-11-21T12:00:00.5"),
    ("data_aktualizacji", "2026-11-21 12:00:00"),
    ("data_aktualizacji", "2026-11-21 12:00:00Z"),
    ("data_aktualizacji", "2026-11-21T12:00:00+0100"),
    ("data_aktualizacji", "2026-11-21T12:00:00+01"),
    ("data_aktualizacji", "2026-11-21t12:00:00z"),
    ("data_aktualizacji", "2026-11-21T24:00:00Z"),
    ("data_aktualizacji", "2026-11-21T12:00:00,5Z"),
    # id_aed nadaje system: tylko zapis kanoniczny (małe litery, z łącznikami)
    ("id_aed", "BCB0AEF5-997B-5080-BEFB-9BBF054CAFE5"),
    ("id_aed", "bcb0aef5997b5080befb9bbf054cafe5"),
    ("id_aed", "urn:uuid:bcb0aef5-997b-5080-befb-9bbf054cafe5"),
    ("id_aed", "{bcb0aef5-997b-5080-befb-9bbf054cafe5}"),
    # zdjecie_url: tylko strona http(s) z poprawnym hostem
    ("zdjecie_url", "ftp://x.pl/a.jpg"),
    ("zdjecie_url", "mailto:a@b.pl"),
    ("zdjecie_url", "https://"),
    ("zdjecie_url", "https://[broken"),
    ("zdjecie_url", "https://@"),    # netloc bez hosta (review #44)
    ("zdjecie_url", "https://:80"),
    ("zdjecie_url", "https://x.pl "),  # spacja na końcu: frictionless przyjmuje, na początku już nie
    # integer: bez podkreśleń w liczbie („1_000” to zapis Pythona, nie liczba z arkusza)
    ("kondygnacja", "1_000"),
}
FRICTIONLESS_CASES = {
    "szerokosc_geo": ["49.75", " 49.75", "49.75 ", "49,75", "nan", "NaN", "inf", "-inf", "1e1", "4.975e1", "+49.75",
                      "49.", ".5", "0x31", "49_75", "54.9", "54.91", "48.99"],
    "kondygnacja": ["3", " 3", "3 ", "-1", "+2", "0.5", "1;2", "1_000", "01", "1e2", "0"],
    "w_budynku": ["tak", "nie", " tak", "tak ", "true", "TAK", "Tak", "1"],
    "data_przegladu": ["2026-11-21", " 2026-11-21", "2026-11-21 ", "2026-02-30", "21.11.2026", "2026-11",
                       "20261121", "2026-W47", "+2026-11-21", "2026-11-21T00:00:00Z", "0001-01-01", "9999-12-31"],
    "data_aktualizacji": ["2026-11-21T12:00:00Z", "2026-11-21T12:00:00+01:00", "2026-11-21T12:00Z",
                          "2026-11-21T12:00:00", "2026-11-21T12:00:00.5Z", "2026-11-21 12:00:00Z",
                          " 2026-11-21T12:00:00Z", "2026-11-21T12:00:00+0100", "2026-11-21t12:00:00z",
                          "2026-11-21T24:00:00Z", "2026-11-21T12:00:60Z", "2026-11-21T12:00:00,5Z",
                          "2026-11-21T12:00:00-00:00", "2026-11-21T12:00:00+14:00", "2026-11-21T12:00:00+01",
                          "2026-11-21T12:00:00.5", "2026-11-21T12:00:00.123456", "2026-11-21 12:00:00"],
    "id_aed": ["bcb0aef5-997b-5080-befb-9bbf054cafe5", "BCB0AEF5-997B-5080-BEFB-9BBF054CAFE5",
               "bcb0aef5997b5080befb9bbf054cafe5", "urn:uuid:bcb0aef5-997b-5080-befb-9bbf054cafe5",
               "{bcb0aef5-997b-5080-befb-9bbf054cafe5}", " bcb0aef5-997b-5080-befb-9bbf054cafe5", "abc"],
    "zdjecie_url": ["https://x.pl/a.jpg", "http://x.pl", "ftp://x.pl/a.jpg", "mailto:a@b.pl", "zdjecie.jpg",
                    "https://[broken", " https://x.pl", "https://x.pl ", "https://", "https://x", "HTTPS://X.PL",
                    "https://x.pl/a b.jpg", "//x.pl/a.jpg", "https://ł.pl/ż.jpg", "https://@", "https://:80"],
    "dostep": ["publiczny", " publiczny", "Publiczny", "nieznany"],
    "kod_teryt_gminy": ["1861011", "186101", " 1861011"],
}


@unittest.skipIf(load_schema() is None, "brak schema/aed.schema.json")
class TestFrictionlessParity(unittest.TestCase):
    """Nigdy łagodniej niż frictionless; ostrzej tylko tam, gdzie mówi STRICTER_THAN_FRICTIONLESS.

    frictionless jest wymagany, tak jak w schema/ (schema/README.md): bez niego test pada, a nie jest
    pomijany – inaczej zwykłe uruchomienie testów po cichu gubi jedyną kontrolę zgodności (review #41).
        pip install "frictionless>=5,<6"
    """

    def setUp(self):
        try:
            from frictionless import Schema
        except ImportError:
            self.fail('brak biblioteki frictionless – pip install "frictionless>=5,<6" (jak w schema/)')
        self.schema = Schema.from_descriptor(load_schema())
        self.fields = {f["name"]: f for f in load_schema()["fields"]}

    def verdicts(self, name, value):
        _, notes = self.schema.get_field(name).read_cell(value)
        return not notes, not validate._check_field(self.fields[name], value)

    def test_same_verdict_as_frictionless(self):
        for name, values in FRICTIONLESS_CASES.items():
            for value in values:
                # Werdykt liczony wewnątrz subTest: wyjątek przy jednej wartości nie przerywa pozostałych.
                with self.subTest(field=name, value=value):
                    theirs, ours = self.verdicts(name, value)
                    if theirs and not ours:
                        self.assertIn((name, value), STRICTER_THAN_FRICTIONLESS, "ostrzej bez opisu w README")
                    else:
                        self.assertEqual(ours, theirs, "łagodniej niż frictionless – dostawca zobaczy fałszywe 0 błędów")

    def test_no_stale_stricter_entries(self):
        for name, value in sorted(STRICTER_THAN_FRICTIONLESS):
            with self.subTest(field=name, value=value):
                # Najpierw czytelny komunikat zamiast KeyError dla pola bez przypadków (review #44).
                self.assertIn(value, FRICTIONLESS_CASES.get(name, []), "wpis bez przypadku w FRICTIONLESS_CASES")
                theirs, ours = self.verdicts(name, value)
                self.assertTrue(theirs and not ours, "wpis nieaktualny – walidatory dają już ten sam werdykt")

    def test_case_count_matches_readme(self):
        # README podaje liczbę przypadków – niech się nie rozjedzie z testem (review #44: „ok. 115” vs 92).
        readme = (Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8")
        total = sum(len(v) for v in FRICTIONLESS_CASES.values())
        self.assertIn(f"na {total} wartościach brzegowych", readme)


if __name__ == "__main__":
    unittest.main()
