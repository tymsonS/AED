"""Testy adaptera OpenAEDMap na próbce eksportu Polski (bez sieci)."""

import tempfile
import unittest
from pathlib import Path

from ingest.adapters.openaedmap import OpenAedMapAdapter, _osm_date
from ingest.cli import load_sources

FIXTURES = Path(__file__).parent / "fixtures"


def records() -> list[dict]:
    source = next(s for s in load_sources() if s["id"] == "osm-openaedmap")
    return OpenAedMapAdapter(source, Path(tempfile.mkdtemp())).records(FIXTURES / "openaedmap-pl.geojson")


class TestOpenAedMap(unittest.TestCase):
    def setUp(self):
        self.recs = records()
        self.by_id = {r["id_zrodlowe"]: r for r in self.recs}

    def test_rekordy_i_identyfikatory(self):
        self.assertEqual(len(self.recs), 6)
        self.assertIn("node/2183365168", self.by_id)
        self.assertEqual(len({r["id_aed"] for r in self.recs}), 6)

    def test_dostepnosc_24h_z_operatorem(self):
        rec = self.by_id["node/2183365168"]
        self.assertEqual(rec["dostep"], "publiczny")
        self.assertEqual((rec["godziny_dostepnosci"], rec["dostepny_24h"]), ("24/7", "tak"))
        self.assertEqual(rec["dysponent_nazwa"], "Urząd Miasta Kołobrzeg")
        self.assertEqual(rec["telefon_kontaktowy"], "+48605353708")
        self.assertEqual(rec["data_weryfikacji"], "2026-04-21")

    def test_dostep_ograniczony_i_kondygnacja(self):
        rec = self.by_id["node/4430364323"]
        self.assertEqual(rec["dostep"], "ograniczony")
        self.assertEqual(rec["dostepny_24h"], "nie")
        self.assertEqual(rec["kondygnacja"], "0")

    def test_telefon_tylko_przy_operatorze(self):
        rec = self.by_id["node/3144781441"]  # telefon bez operatora – może być prywatny
        self.assertEqual(rec["dostep"], "prywatny")
        self.assertEqual(rec["telefon_kontaktowy"], "")

    def test_brak_godzin_i_dostepu(self):
        rec = self.by_id["node/477958354"]
        self.assertEqual(rec["dostep"], "")
        self.assertEqual((rec["godziny_dostepnosci"], rec["dostepny_24h"]), ("nieznane", "nieznane"))
        self.assertEqual(rec["w_budynku"], "true")

    def test_metadane_zrodla(self):
        for rec in self.recs:
            self.assertEqual(rec["zrodlo"], "osm-openaedmap")
            self.assertEqual(rec["licencja"], "ODbL-1.0")
            self.assertEqual(rec["metoda_weryfikacji"], "zgloszenie_spoleczne")

    def test_daty_osm(self):
        self.assertEqual(_osm_date("2023-02"), "2023-02-01")
        self.assertEqual(_osm_date("12.05.2024"), "")


if __name__ == "__main__":
    unittest.main()
