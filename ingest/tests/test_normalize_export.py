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


@unittest.skipIf(load_schema() is None, "schema/aed.schema.json jeszcze nie jest na tej gałęzi (PR #9)")
class TestZgodnoscZeSchematem(unittest.TestCase):
    def test_lista_pol_zgodna_ze_schematem(self):
        self.assertEqual(tuple(f["name"] for f in load_schema()["fields"]), FALLBACK_FIELDS)


if __name__ == "__main__":
    unittest.main()
