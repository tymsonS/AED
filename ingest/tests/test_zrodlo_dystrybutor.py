"""Testy źródła „dystrybutor”: poziom zaufania, scalanie po id_aed, adapter (bez sieci)."""

import csv
import tempfile
import unittest
from pathlib import Path

from ingest import export, gaps
from ingest.adapters.dystrybutor import DystrybutorAdapter
from ingest.cli import load_sources
from ingest.fields import field_names
from ingest.tests.test_gminy_gaps import aed

TRUST = {"danegovpl-krosno": 1, "dystrybutor": 2, "osm-openaedmap": 3}


class TestPoziomZaufania(unittest.TestCase):
    def test_kilka_zrodel(self):
        self.assertEqual(gaps.trust_level("danegovpl-krosno;dystrybutor", TRUST), 1)
        self.assertEqual(gaps.trust_level("dystrybutor", TRUST), 2)
        self.assertEqual(gaps.trust_level("osm-openaedmap;dystrybutor", TRUST), 2)
        self.assertEqual(gaps.trust_level("nieznane", TRUST), 3)
        self.assertEqual(gaps.trust_level("", TRUST), 3)

    def test_rekord_z_kilku_zrodel_jest_zweryfikowany(self):
        rec = aed(49.75, 21.75, zrodlo="danegovpl-krosno;dystrybutor", id_aed="a")
        self.assertTrue(gaps.verification([rec], TRUST)[0]["zweryfikowany"])


class TestScalaniePoIdAed(unittest.TestCase):
    def test_potwierdzony_zastepuje_oryginal(self):
        osm = aed(49.75, 21.75, id_aed="a")
        moved = aed(49.76, 21.75, zrodlo="dystrybutor", id_aed="a")  # inne_miejsce, ponad 1 km dalej
        other = aed(49.80, 21.75, id_aed="b")
        kept, replaced = gaps.supersede([osm, other, moved], TRUST)
        self.assertEqual(replaced, 1)
        self.assertEqual([(r["id_aed"], r["zrodlo"]) for r in kept], [("b", "osm-openaedmap"), ("a", "dystrybutor")])

    def test_instytucja_wygrywa_z_osm_i_kolejnosc_bez_znaczenia(self):
        inst = aed(49.75, 21.75, zrodlo="danegovpl-krosno;dystrybutor", id_aed="a", lokalizacje_potwierdzil="CR")
        orig = aed(49.75, 21.75, zrodlo="danegovpl-krosno", id_aed="a")
        for order in ([orig, inst], [inst, orig]):
            kept, _ = gaps.supersede(order, TRUST)
            self.assertEqual([r["zrodlo"] for r in kept], ["danegovpl-krosno;dystrybutor"])  # remis: wygrywa potwierdzony

    def test_rekordy_bez_id_zostaja(self):
        kept, replaced = gaps.supersede([aed(1, 1, id_aed=""), aed(2, 2, id_aed="")], TRUST)
        self.assertEqual((len(kept), replaced), (2, 0))


class TestOpisWAedApp(unittest.TestCase):
    def test_opis_z_potwierdzeniem(self):
        rec = aed(49.75, 21.75, zrodlo="dystrybutor", lokalizacje_potwierdzil="Centrum Ratownictwa X",
                  data_weryfikacji="2026-11-20")
        st = gaps.verification([rec], TRUST)[0]
        props = export.app_properties(rec, st, "Dystrybutor")
        self.assertEqual(props["status_weryfikacji"], "zweryfikowany")
        self.assertEqual(props["opis_weryfikacji"], "Lokalizację potwierdził: Centrum Ratownictwa X (2026-11-20).")

    def test_dysponent_z_pierwszego_znanego_zrodla(self):
        self.assertEqual(export._dysponent("danegovpl-krosno;dystrybutor", {"danegovpl-krosno": "UM Krosna"}),
                         "UM Krosna")
        self.assertEqual(export._dysponent("x;y", {}), "x;y")


class TestAdapterDystrybutor(unittest.TestCase):
    def setUp(self):
        self.source = next(s for s in load_sources() if s["id"] == "dystrybutor")
        self.root = Path(tempfile.mkdtemp())
        self.adapter = DystrybutorAdapter(self.source, self.root)
        self.adapter.raw_dir.mkdir(parents=True)

    def test_rejestr_zrodel(self):
        self.assertEqual((self.source["poziom_zaufania"], self.source["opcjonalne"], self.source["wszystkie_pliki"]),
                         (2, True, True))

    def test_czyta_wzorcowy_csv_i_usuniete(self):
        path = self.adapter.raw_dir / "resource-dystrybutor-18.csv"
        with path.open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(field_names()))
            w.writeheader()
            w.writerow({k: "" for k in field_names()} | {"id_aed": "a", "zrodlo": "dystrybutor"})
        (self.adapter.raw_dir / "usuniete-dystrybutor-18.csv").write_text("id_aed,zrodlo\nb,osm-openaedmap\n",
                                                                          encoding="utf-8")
        recs = self.adapter.records(path)
        self.assertEqual((recs[0]["id_aed"], recs[0]["_uwagi"]), ("a", []))
        self.assertTrue(set(field_names()) <= set(recs[0]))
        self.assertEqual(self.adapter.removed_ids(), {"b"})

    def test_fetch_to_zrodlo_lokalne(self):
        with self.assertRaises(RuntimeError):
            self.adapter.fetch()


if __name__ == "__main__":
    unittest.main()
