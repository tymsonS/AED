"""Testy źródła „dystrybutor”: poziom zaufania, scalanie po id_aed, adapter (bez sieci)."""

import csv
import tempfile
import unittest
from pathlib import Path

from ingest import export, gaps
from ingest.adapters.dystrybutor import DystrybutorAdapter
from ingest.cli import load_sources
from ingest.fields import field_names
from ingest.tests.test_municipalities_gaps import aed

TRUST = {"danegovpl-krosno": 1, "dystrybutor": 2, "osm-openaedmap": 3}


class TestTrustLevel(unittest.TestCase):
    def test_multiple_sources(self):
        self.assertEqual(gaps.trust_level("danegovpl-krosno;dystrybutor", TRUST), 1)
        self.assertEqual(gaps.trust_level("dystrybutor", TRUST), 2)
        self.assertEqual(gaps.trust_level("osm-openaedmap;dystrybutor", TRUST), 2)
        self.assertEqual(gaps.trust_level("nieznane", TRUST), 3)
        self.assertEqual(gaps.trust_level("", TRUST), 3)

    def test_multi_source_record_is_verified(self):
        rec = aed(49.75, 21.75, zrodlo="danegovpl-krosno;dystrybutor", id_aed="a")
        self.assertTrue(gaps.verification([rec], TRUST)[0]["zweryfikowany"])


class TestSupersedeById(unittest.TestCase):
    def test_confirmed_replaces_original(self):
        osm = aed(49.75, 21.75, id_aed="a")
        moved = aed(49.76, 21.75, zrodlo="dystrybutor", id_aed="a")  # inne_miejsce, ponad 1 km dalej
        other = aed(49.80, 21.75, id_aed="b")
        kept, replaced = gaps.supersede([osm, other, moved], TRUST)
        self.assertEqual(replaced, 1)
        self.assertEqual([(r["id_aed"], r["zrodlo"]) for r in kept], [("b", "osm-openaedmap"), ("a", "dystrybutor")])

    def test_institution_wins_order_independent(self):
        inst = aed(49.75, 21.75, zrodlo="danegovpl-krosno;dystrybutor", id_aed="a", lokalizacje_potwierdzil="CR")
        orig = aed(49.75, 21.75, zrodlo="danegovpl-krosno", id_aed="a")
        for order in ([orig, inst], [inst, orig]):
            kept, _ = gaps.supersede(order, TRUST)
            self.assertEqual([r["zrodlo"] for r in kept], ["danegovpl-krosno;dystrybutor"])  # remis: wygrywa potwierdzony

    def test_records_without_id_kept(self):
        kept, replaced = gaps.supersede([aed(1, 1, id_aed=""), aed(2, 2, id_aed="")], TRUST)
        self.assertEqual((len(kept), replaced), (2, 0))


class TestAppExportDescription(unittest.TestCase):
    def test_description_with_confirmation(self):
        rec = aed(49.75, 21.75, zrodlo="dystrybutor", lokalizacje_potwierdzil="Centrum Ratownictwa X",
                  data_weryfikacji="2026-11-20")
        st = gaps.verification([rec], TRUST)[0]
        props = export.app_properties(rec, st, "Dystrybutor")
        self.assertEqual(props["status_weryfikacji"], "zweryfikowany")
        self.assertEqual(props["opis_weryfikacji"], "Lokalizację potwierdził: Centrum Ratownictwa X (2026-11-20).")

    def test_owner_from_first_known_source(self):
        self.assertEqual(export._dysponent("danegovpl-krosno;dystrybutor", {"danegovpl-krosno": "UM Krosna"}),
                         "UM Krosna")
        self.assertEqual(export._dysponent("x;y", {}), "x;y")


class TestDistributorAdapter(unittest.TestCase):
    def setUp(self):
        self.source = next(s for s in load_sources() if s["id"] == "dystrybutor")
        self.root = Path(tempfile.mkdtemp())
        self.adapter = DystrybutorAdapter(self.source, self.root)
        self.adapter.raw_dir.mkdir(parents=True)

    def test_source_registry(self):
        self.assertEqual((self.source["poziom_zaufania"], self.source["opcjonalne"], self.source["wszystkie_pliki"]),
                         (2, True, True))

    def test_reads_model_csv_and_removed(self):
        path = self.adapter.raw_dir / "resource-dystrybutor-18.csv"
        with path.open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(field_names()))
            w.writeheader()
            w.writerow({k: "" for k in field_names()} | {"id_aed": "a", "zrodlo": "dystrybutor"})
        (self.adapter.raw_dir / "usuniete-dystrybutor-18--cr-x.csv").write_text(
            "id_aed,zrodlo,data_sprawdzenia,zglosil,poinformowano_dysponenta\n"
            "b,osm-openaedmap,2026-11-19,CR X,\n"
            "c,danegovpl-krosno,2026-11-19,CR X,2026-11-20\n", encoding="utf-8")
        recs = self.adapter.records(path)
        self.assertEqual((recs[0]["id_aed"], recs[0]["_uwagi"]), ("a", []))
        self.assertTrue(set(field_names()) <= set(recs[0]))
        self.assertEqual(self.adapter.missing_reports(), {
            "b": {"opis": "CR X, 2026-11-19", "poinformowano": ""},
            "c": {"opis": "CR X, 2026-11-19", "poinformowano": "2026-11-20"}})

    def test_notification_date_kept_across_files(self):
        # Review #42, pkt 3: późniejszy (alfabetycznie) plik z pustą datą nie kasuje wcześniejszej.
        header = "id_aed,zrodlo,data_sprawdzenia,zglosil,poinformowano_dysponenta\n"
        (self.adapter.raw_dir / "usuniete-a--cr-x.csv").write_text(
            header + "g,danegovpl-krosno,2026-11-19,CR X,2026-11-20\n", encoding="utf-8")
        (self.adapter.raw_dir / "usuniete-b--firma-y.csv").write_text(
            header + "g,danegovpl-krosno,2026-11-21,Firma Y,\n", encoding="utf-8")
        self.assertEqual(self.adapter.missing_reports()["g"],
                         {"opis": "CR X, 2026-11-19", "poinformowano": "2026-11-20"})  # opis i data z jednego zgłoszenia

    def test_fetch_local_source(self):
        with self.assertRaises(RuntimeError):
            self.adapter.fetch()

    def test_old_list_with_zoned_date_converted_to_polish_time(self):
        # Review #63: listy wczytane przed zmianą mają „…Z”; stare wiersze są zachowywane przy
        # każdym wczytaniu, więc adapter przelicza je na czas polski bez strefy.
        path = self.adapter.raw_dir / "resource-dystrybutor-18.csv"
        with path.open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(field_names()))
            w.writeheader()
            for i, stamp in enumerate(["2026-11-21T12:00:00Z", "2026-11-21T13:00:00"]):
                w.writerow({k: "" for k in field_names()} | {"id_aed": str(i), "data_aktualizacji": stamp})
        recs = self.adapter.records(path)
        self.assertEqual([r["data_aktualizacji"] for r in recs], ["2026-11-21T13:00:00", "2026-11-21T13:00:00"])
        self.assertIn("przeliczona na czas polski", recs[0]["_uwagi"][0])
        self.assertEqual(recs[1]["_uwagi"], [])


class TestReview37Fixes(unittest.TestCase):
    def test_file_name_with_distributor(self):
        from ingest.distributor import slug
        self.assertEqual(slug("Centrum Ratownictwa Łódź"), "centrum-ratownictwa-lodz")
        self.assertEqual(slug("Firma „AED-Serwis” sp. z o.o."), "firma-aed-serwis-sp-z-o-o")
        self.assertEqual(slug("!!!"), "dystrybutor")
        self.assertNotEqual(slug("Firma A"), slug("Firma B"))

    def test_reported_missing_removes_osm_flags_institution(self):
        from ingest.cli import _apply_missing_reports
        osm = aed(49.75, 21.75, id_aed="o")
        inst = aed(49.76, 21.75, zrodlo="danegovpl-krosno", id_aed="i", dysponent_nazwa="UM Krosna")
        other = aed(49.77, 21.75, id_aed="x")
        report = {"opis": "CR X, 2026-11-19", "poinformowano": ""}
        kept = _apply_missing_reports([osm, inst, other], {"o": report, "i": report}, {"danegovpl-krosno"})
        self.assertEqual([r["id_aed"] for r in kept], ["i", "x"])
        self.assertEqual(inst["_zgloszony_brak"], "CR X, 2026-11-19")
        st = gaps.verification(kept, TRUST)
        self.assertEqual((st[0]["zweryfikowany"], st[0]["zgloszony_brak"]), (False, True))
        props = export.app_properties(inst, st[0], "UM Krosna")
        self.assertEqual(props["status_weryfikacji"], "niezweryfikowany")
        self.assertIn("zgłosił brak urządzenia", props["opis_weryfikacji"])
        self.assertIn("UM Krosna", props["opis_weryfikacji"])

    def test_institution_record_removed_only_after_notice(self):
        # Review #37, krok 2: data poinformowania dysponenta = usuwamy z naszych wyników jak OSM.
        from ingest.cli import _apply_missing_reports
        inst = aed(49.76, 21.75, zrodlo="danegovpl-krosno", id_aed="i")
        other = aed(49.77, 21.75, id_aed="x")
        kept = _apply_missing_reports([inst, other], {"i": {"opis": "CR X, 2026-11-19",
                                                             "poinformowano": "2026-11-20"}}, {"danegovpl-krosno"})
        self.assertEqual([r["id_aed"] for r in kept], ["x"])
        self.assertNotIn("_zgloszony_brak", inst)

    def test_reported_missing_on_distributor_list(self):
        from ingest import distributor
        inst = aed(49.76, 21.75, zrodlo="danegovpl-krosno", id_aed="i", dysponent_nazwa="UM Krosna",
                   kod_teryt_gminy="1861011", gmina="Krosno", _zgloszony_brak="CR X, 2026-11-19")
        meta = distributor.DistributorMeta(obszar=["1861011"], dystrybutor="CR Y")
        rows, _ = distributor.build_worklist([inst], gaps.verification([inst], TRUST), meta)
        self.assertEqual(rows[0]["priorytet"], 1)
        self.assertIn("wyjaśnij z dysponentem", rows[0]["powod"])

    def test_institution_source_id_kept(self):
        from datetime import date

        from ingest import distributor
        from ingest import distributor_import as di
        from ingest.fields import empty_record
        orig = empty_record() | {"id_aed": "i", "zrodlo": "danegovpl-krosno", "licencja": "CC0-1.0",
                                 "id_zrodlowe": "17", "szerokosc_geo": "49.75", "dlugosc_geo": "21.75"}
        row = {k: "" for k in distributor.KOLUMNY} | {
            "id_aed": "i", "zrodlo": "danegovpl-krosno", "szerokosc_geo": "49.75", "dlugosc_geo": "21.75",
            "wynik_sprawdzenia": "potwierdzam", "data_sprawdzenia": "2026-11-20", "lokalizacje_potwierdzil": "CR"}
        res = di.import_worklist([row], {"i": orig}, di.ImportMeta(dystrybutor="CR"), date(2026, 11, 21))
        self.assertEqual(res["potwierdzone"][0]["id_zrodlowe"], "17")


if __name__ == "__main__":
    unittest.main()
