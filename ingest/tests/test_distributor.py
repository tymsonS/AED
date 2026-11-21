"""Testy listy AED do potwierdzenia dla dystrybutora (bez sieci)."""

import csv
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from ingest import distributor, gaps
from ingest.tests.test_gminy_gaps import TRUST, aed

TODAY = date(2026, 11, 21)


def rec(lat, lon, teryt, **kw):
    r = aed(lat, lon, kod_teryt_gminy=teryt, gmina=f"G{teryt}", **kw)
    return r


class TestListaDystrybutora(unittest.TestCase):
    def setUp(self):
        self.records = [
            rec(49.75, 21.75, "1861011", zrodlo="danegovpl-krosno", id_aed="v1",
                dysponent_nazwa="Urząd Miasta Krosna", licencja="CC0-1.0"),
            rec(49.7502, 21.75, "1861011", id_aed="dup", id_zrodlowe="node/1"),     # ten sam AED co v1
            rec(49.76, 21.75, "1861011", id_aed="bez", id_zrodlowe="node/2"),       # bez dysponenta
            rec(49.77, 21.75, "1861011", id_aed="stary", id_zrodlowe="node/3",
                dysponent_nazwa="Szkoła", data_weryfikacji="2024-01-10"),
            rec(49.78, 21.75, "1862042", id_aed="swiezy", id_zrodlowe="node/4",
                dysponent_nazwa="OSP", data_weryfikacji="2026-06-01"),
            rec(52.3, 21.1, "1434021", id_aed="inne_woj", id_zrodlowe="node/5"),
            aed("", "", id_aed="bez_wsp"),                                          # bez gminy
        ]
        self.statuses = gaps.verification(self.records, TRUST)

    def worklist(self, obszar):
        meta = distributor.DistributorMeta(obszar=obszar, dystrybutor="Centrum Ratownictwa X")
        return distributor.build_worklist(self.records, self.statuses, meta, TODAY)

    def test_obszar_wojewodztwa(self):
        rows, summ = self.worklist(["18"])
        self.assertEqual({r["id_aed"] for r in rows}, {"v1", "bez", "stary", "swiezy"})
        self.assertEqual(summ["pominiete_duplikaty_osm"], 1)
        self.assertEqual(summ["zweryfikowane"], 1)
        self.assertEqual(summ["nazwa_obszaru"], "województwo podkarpackie")

    def test_obszar_gminy_i_powiatu_razem(self):
        rows, _ = self.worklist(["1861011", "1862"])
        self.assertEqual(len(rows), 4)
        rows, _ = self.worklist(["1862"])
        self.assertEqual([r["id_aed"] for r in rows], ["swiezy"])

    def test_priorytety(self):
        rows, summ = self.worklist(["18"])
        prio = {r["id_aed"]: r["priorytet"] for r in rows}
        self.assertEqual(prio, {"bez": 1, "stary": 2, "swiezy": 3, "v1": 4})
        self.assertIn("brak dysponenta", next(r for r in rows if r["id_aed"] == "bez")["powod"])
        self.assertEqual(sum(summ["wg_priorytetu"].values()), 4)

    def test_kolumny_dystrybutora_puste_i_link_do_osm(self):
        rows, _ = self.worklist(["18"])
        for r in rows:
            for k in distributor.KOLUMNY_DYSTRYBUTORA:
                self.assertEqual(r[k], "", k)  # nic nie potwierdzamy za dystrybutora
        by_id = {r["id_aed"]: r for r in rows}
        self.assertEqual(by_id["bez"]["mapa_url"], "https://www.openstreetmap.org/node/2")
        self.assertIn("mlat=49.75", by_id["v1"]["mapa_url"])

    def test_bledny_obszar(self):
        for obszar in ([], ["123"], ["99"]):
            with self.assertRaises(distributor.DistributorError):
                distributor.DistributorMeta(obszar=obszar, dystrybutor="X").check()
        with self.assertRaises(distributor.DistributorError):
            distributor.DistributorMeta(obszar=["18"], dystrybutor=" ").check()

    def test_pliki_pakietu(self):
        meta = distributor.DistributorMeta(obszar=["18"], dystrybutor="Centrum Ratownictwa X")
        out = Path(tempfile.mkdtemp())
        paths = distributor.write_distributor_package(self.records, self.statuses, meta, out, TODAY)
        raw = paths["csv"].read_bytes()
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))  # BOM dla Excela
        with paths["csv"].open(encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(tuple(rows[0]), distributor.KOLUMNY)
        self.assertEqual([r["lp"] for r in rows], ["1", "2", "3", "4"])
        geo = json.loads(paths["geojson"].read_text(encoding="utf-8"))
        self.assertEqual(len(geo["features"]), 4)
        text = paths["instrukcja"].read_text(encoding="utf-8")
        self.assertIn("ODbL", text)
        self.assertIn("Centrum Ratownictwa X", text)

    def test_pusty_obszar(self):
        meta = distributor.DistributorMeta(obszar=["02"], dystrybutor="X")
        with self.assertRaises(distributor.DistributorError):
            distributor.write_distributor_package(self.records, self.statuses, meta, Path(tempfile.mkdtemp()))


if __name__ == "__main__":
    unittest.main()
