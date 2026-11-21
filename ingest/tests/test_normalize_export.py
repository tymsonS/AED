"""Testy normalizacji, eksportu i zgodności z schema/ (bez sieci)."""

import csv
import json
import tempfile
import unittest
from pathlib import Path

from ingest import export, normalize
from ingest.fields import FALLBACK_FIELDS, load_schema


class TestNormalize(unittest.TestCase):
    def test_zamiana_wspolrzednych(self):
        self.assertEqual(normalize.fix_coordinates(52.2, 21.0), (52.2, 21.0, False))
        self.assertEqual(normalize.fix_coordinates(21.0, 52.2), (52.2, 21.0, True))
        self.assertFalse(normalize.fix_coordinates(10.0, 10.0)[2])

    def test_telefon(self):
        self.assertEqual(normalize.normalize_phone("16 677 95 00"), "+48166779500")
        self.assertEqual(normalize.normalize_phone("16 677 95"), "")  # za krótki
        self.assertEqual(normalize.normalize_phone("0048 22 123 45 67"), "+48221234567")
        self.assertEqual(normalize.normalize_phone(""), "")

    def test_adres_bez_kodu(self):
        self.assertEqual(normalize.parse_address("ul. Długa 5")["ulica"], "Długa")


class TestExport(unittest.TestCase):
    def test_csv_i_geojson(self):
        rec = {name: "" for name in FALLBACK_FIELDS}
        rec.update(szerokosc_geo="52.1", dlugosc_geo="21.0", nazwa_obiektu="Test", _uwagi=["x"])
        out = Path(tempfile.mkdtemp())
        export.write_csv([rec], out / "aed.csv")
        export.write_geojson([rec], out / "aed.geojson")
        with (out / "aed.csv").open(encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(rows[0]["nazwa_obiektu"], "Test")
        self.assertNotIn("_uwagi", rows[0])
        geo = json.loads((out / "aed.geojson").read_text(encoding="utf-8"))
        self.assertEqual(geo["features"][0]["geometry"]["coordinates"], [21.0, 52.1])

    def test_geojson_dla_app(self):
        base = {name: "" for name in FALLBACK_FIELDS}
        ver = dict(base, szerokosc_geo="52.1", dlugosc_geo="21.0", zrodlo="gmina", _uwagi=["x"])
        osm = dict(base, szerokosc_geo="52.2", dlugosc_geo="21.1", zrodlo="osm")
        bad = dict(base, szerokosc_geo="", dlugosc_geo="", zrodlo="osm")
        statuses = [
            {"poziom_zaufania": 1, "zweryfikowany": True, "poza_obszarem_dysponenta": False, "ten_sam_co": ""},
            {"poziom_zaufania": 3, "zweryfikowany": False, "poza_obszarem_dysponenta": False, "ten_sam_co": ""},
            {"poziom_zaufania": 3, "zweryfikowany": False, "poza_obszarem_dysponenta": False, "ten_sam_co": ""},
        ]
        out = Path(tempfile.mkdtemp()) / "aed-app.geojson"
        n = export.write_app_geojson([ver, osm, bad], statuses, {"gmina": "Urząd Miasta X"}, out)
        self.assertEqual(n, 2)  # rekord bez współrzędnych pominięty
        props = [f["properties"] for f in json.loads(out.read_text(encoding="utf-8"))["features"]]
        self.assertEqual(props[0]["status_weryfikacji"], "zweryfikowany")
        self.assertIn("Urząd Miasta X", props[0]["opis_weryfikacji"])
        self.assertEqual(props[1]["status_weryfikacji"], "niezweryfikowany")
        self.assertIn("osm", props[1]["opis_weryfikacji"])  # nieznany dysponent -> id źródła
        self.assertNotIn("_uwagi", props[0])
        # Lekka wersja: tylko pola potrzebne app/, bez np. REGON i dat przeglądów.
        self.assertEqual(set(props[0]), set(export.APP_FIELDS) | {
            "poziom_zaufania", "status_weryfikacji", "opis_weryfikacji", "ten_sam_co"})
        self.assertTrue(set(export.APP_FIELDS) <= set(FALLBACK_FIELDS))


@unittest.skipIf(load_schema() is None, "brak schema/aed.schema.json")
class TestZgodnoscZeSchematem(unittest.TestCase):
    def test_lista_pol_zgodna_ze_schematem(self):
        self.assertEqual(tuple(f["name"] for f in load_schema()["fields"]), FALLBACK_FIELDS)


if __name__ == "__main__":
    unittest.main()
