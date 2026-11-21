"""Testy wczytania listy wypełnionej przez dystrybutora (bez sieci)."""

import csv
import json
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

from ingest import distributor
from ingest import distributor_import as di
from ingest.fields import empty_record

TODAY = date(2026, 11, 21)
NOW = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)
META = di.ImportMeta(dystrybutor="Centrum Ratownictwa X")


def orig(id_aed, zrodlo, licencja, **kw):
    r = empty_record()
    r.update(id_aed=id_aed, zrodlo=zrodlo, licencja=licencja, id_zrodlowe=f"src-{id_aed}",
             szerokosc_geo="49.750000", dlugosc_geo="21.750000", gmina="Krosno",
             kod_teryt_gminy="1861011", wojewodztwo="podkarpackie", _uwagi=[])
    r.update(kw)
    return r


ORIGINALS = {
    "osm1": orig("osm1", "osm-openaedmap", "ODbL-1.0", nazwa_obiektu="Nazwa z OSM", opis_lokalizacji="Opis z OSM",
                 dysponent_nazwa="Operator z OSM", dostep="publiczny", godziny_dostepnosci="24/7",
                 dostepny_24h="tak", ulica="Ulica z OSM", metoda_weryfikacji="zgloszenie_spoleczne"),
    "inst1": orig("inst1", "danegovpl-krosno", "CC0-1.0", nazwa_obiektu="Pływalnia", dysponent_nazwa="UM Krosna",
                  ulica="Jasna", dostep="nieznany", godziny_dostepnosci="nieznane", dostepny_24h="nieznane",
                  status="nieznany", metoda_weryfikacji="import"),
}


def row(id_aed, zrodlo, **kw):
    r = {k: "" for k in distributor.KOLUMNY}
    r.update(id_aed=id_aed, zrodlo=zrodlo, szerokosc_geo="49.750000", dlugosc_geo="21.750000")
    r.update(kw)
    return r


def run(*rows):
    return di.import_worklist(list(rows), ORIGINALS, META, TODAY, NOW)


class TestWczytanie(unittest.TestCase):
    def test_wiersz_osm_bez_tresci_z_osm(self):
        res = run(row("osm1", "osm-openaedmap", wynik_sprawdzenia="potwierdzam", data_sprawdzenia="2026-11-20",
                      lokalizacje_potwierdzil="Centrum Ratownictwa X", nazwa_obiektu_poprawiona="SP nr 5",
                      dysponent_poprawiony="Gmina Krosno"))
        rec = res["potwierdzone"][0]
        self.assertEqual((rec["nazwa_obiektu"], rec["dysponent_nazwa"]), ("SP nr 5", "Gmina Krosno"))
        for key in ("opis_lokalizacji", "ulica"):
            self.assertEqual(rec[key], "", key)  # review #29: nic z ODbL w zbiorze CC
        self.assertEqual((rec["dostep"], rec["godziny_dostepnosci"], rec["dostepny_24h"]),
                         ("nieznany", "nieznane", "nieznane"))
        self.assertEqual((rec["metoda_weryfikacji"], rec["data_weryfikacji"]), ("dystrybutor", "2026-11-20"))
        self.assertEqual((rec["zrodlo"], rec["licencja"]), ("dystrybutor", "CC-BY-4.0"))
        self.assertEqual(rec["gmina"], "Krosno")  # wyliczona przez nas z PRG, nie z OSM
        self.assertEqual(res["problemy"], [])

    def test_wiersz_instytucji_zachowuje_pola_i_zrodlo(self):
        res = run(row("inst1", "danegovpl-krosno", wynik_sprawdzenia="potwierdzam", data_sprawdzenia="21.11.2026",
                      lokalizacje_potwierdzil="Centrum Ratownictwa X",
                      odpowiedzialny_za_stan_techniczny="Serwis X"))
        rec = res["potwierdzone"][0]
        self.assertEqual((rec["nazwa_obiektu"], rec["ulica"]), ("Pływalnia", "Jasna"))
        self.assertEqual(rec["zrodlo"], "danegovpl-krosno;dystrybutor")
        self.assertEqual(rec["licencja"], "CC0-1.0")
        self.assertEqual(rec["data_weryfikacji"], "2026-11-21")  # DD.MM.RRRR z Excela
        self.assertEqual(rec["odpowiedzialny_za_stan_techniczny"], "Serwis X")

    def test_osm_bez_nazwy_i_dysponenta_daje_uwagi(self):
        res = run(row("osm1", "osm-openaedmap", wynik_sprawdzenia="potwierdzam", data_sprawdzenia="2026-11-20"))
        msgs = " ".join(p["komunikat"] for p in res["problemy"])
        self.assertIn("nazwa_obiektu_poprawiona", msgs)
        self.assertIn("dysponent_poprawiony", msgs)
        self.assertIn("wpisano dystrybutora", msgs)
        self.assertEqual(res["potwierdzone"][0]["lokalizacje_potwierdzil"], "Centrum Ratownictwa X")
        self.assertEqual(res["potwierdzone"][0]["nazwa_obiektu"], "")

    def test_inne_miejsce_wymaga_nowych_wspolrzednych(self):
        same = run(row("osm1", "osm-openaedmap", wynik_sprawdzenia="inne_miejsce", data_sprawdzenia="2026-11-20"))
        self.assertEqual(same["potwierdzone"], [])
        self.assertIn("współrzędne bez zmian", same["problemy"][0]["komunikat"])
        moved = run(row("osm1", "osm-openaedmap", wynik_sprawdzenia="inne_miejsce", data_sprawdzenia="2026-11-20",
                        szerokosc_geo="49,7503", nazwa_obiektu_poprawiona="Hala", dysponent_poprawiony="MOSiR"))
        rec = moved["potwierdzone"][0]
        self.assertEqual(rec["szerokosc_geo"], "49.750300")  # przecinek dziesiętny z Excela
        self.assertEqual(rec["gmina"], "")  # do wyliczenia od nowa (CLI: gminy.enrich)
        self.assertTrue(rec["_inne_miejsce"])

    def test_brak_urzadzenia_i_niesprawdzone(self):
        res = run(row("osm1", "osm-openaedmap", wynik_sprawdzenia="brak_urzadzenia", data_sprawdzenia="2026-11-19",
                      uwagi_dystrybutora="zdjęty"),
                  row("inst1", "danegovpl-krosno"))
        self.assertEqual(res["potwierdzone"], [])
        self.assertEqual(res["do_usuniecia"][0]["id_zrodlowe"], "src-osm1")
        self.assertEqual(res["pominiete"], ["inst1"])

    def test_bledne_wiersze(self):
        res = run(
            row("osm1", "osm-openaedmap", wynik_sprawdzenia="tak", data_sprawdzenia="2026-11-20"),
            row("obcy", "osm-openaedmap", wynik_sprawdzenia="potwierdzam", data_sprawdzenia="2026-11-20"),
            row("inst1", "osm-openaedmap", wynik_sprawdzenia="potwierdzam", data_sprawdzenia="2026-11-20"),
            row("inst1", "danegovpl-krosno", wynik_sprawdzenia="potwierdzam", data_sprawdzenia="2062-01-01"),
            row("inst1", "danegovpl-krosno", wynik_sprawdzenia="potwierdzam", data_sprawdzenia="2026-11-20",
                szerokosc_geo="10.0", dlugosc_geo="10.0"),
        )
        self.assertEqual(res["potwierdzone"], [])
        self.assertEqual([p["wiersz"] for p in res["problemy"]], [2, 3, 4, 5, 6])

    def test_powtorzony_aed(self):
        r = row("inst1", "danegovpl-krosno", wynik_sprawdzenia="potwierdzam", data_sprawdzenia="2026-11-20",
                lokalizacje_potwierdzil="CR X")
        res = run(r, dict(r))
        self.assertEqual(len(res["potwierdzone"]), 1)
        self.assertIn("drugi raz", res["problemy"][-1]["komunikat"])

    def test_meta(self):
        for bad in (di.ImportMeta(dystrybutor=" "), di.ImportMeta(dystrybutor="X", zrodlo="Dystrybutor CR"),
                    di.ImportMeta(dystrybutor="X", licencja="ODbL-1.0")):
            with self.assertRaises(di.DistributorImportError):
                bad.check()


class TestPlikZExcela(unittest.TestCase):
    def write(self, text: str, encoding: str) -> Path:
        path = Path(tempfile.mkdtemp()) / "lista.csv"
        path.write_bytes(text.encode(encoding))
        return path

    def test_srednik_cp1250_i_apostrof(self):
        header = ";".join(distributor.KOLUMNY)
        values = {k: "" for k in distributor.KOLUMNY}
        values.update(id_aed="inst1", zrodlo="danegovpl-krosno", nazwa_obiektu="'-Rynek", uwagi_dystrybutora="Żółw")
        path = self.write(header + "\n" + ";".join(values[k] for k in distributor.KOLUMNY) + "\n", "cp1250")
        rows = di.read_worklist(path)
        self.assertEqual(rows[0]["uwagi_dystrybutora"], "Żółw")
        self.assertEqual(rows[0]["nazwa_obiektu"], "-Rynek")  # apostrof z excel_safe() zdjęty

    def test_plik_z_innymi_kolumnami(self):
        with self.assertRaises(di.DistributorImportError):
            di.read_worklist(self.write("a,b\n1,2\n", "utf-8"))

    def test_zapis_wyniku(self):
        res = run(row("inst1", "danegovpl-krosno", wynik_sprawdzenia="potwierdzam", data_sprawdzenia="2026-11-20",
                      lokalizacje_potwierdzil="CR X"),
                  row("osm1", "osm-openaedmap", wynik_sprawdzenia="brak_urzadzenia", data_sprawdzenia="2026-11-20"))
        paths = di.write_import(res, META, Path(tempfile.mkdtemp()))
        with paths["csv"].open(encoding="utf-8") as fh:
            recs = list(csv.DictReader(fh))
        self.assertNotIn("_inne_miejsce", recs[0])
        report = json.loads(paths["raport"].read_text(encoding="utf-8"))
        self.assertEqual((report["potwierdzone"], report["do_usuniecia"]), (1, 1))


if __name__ == "__main__":
    unittest.main()
