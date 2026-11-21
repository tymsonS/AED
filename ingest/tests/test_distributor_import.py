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


class TestImport(unittest.TestCase):
    def test_osm_row_without_osm_content(self):
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

    def test_institution_row_keeps_fields_and_source(self):
        res = run(row("inst1", "danegovpl-krosno", wynik_sprawdzenia="potwierdzam", data_sprawdzenia="21.11.2026",
                      lokalizacje_potwierdzil="Centrum Ratownictwa X",
                      odpowiedzialny_za_stan_techniczny="Serwis X"))
        rec = res["potwierdzone"][0]
        self.assertEqual((rec["nazwa_obiektu"], rec["ulica"]), ("Pływalnia", "Jasna"))
        self.assertEqual(rec["zrodlo"], "danegovpl-krosno;dystrybutor")
        self.assertEqual(rec["licencja"], "CC0-1.0")
        self.assertEqual(rec["data_weryfikacji"], "2026-11-21")  # DD.MM.RRRR z Excela
        self.assertEqual(rec["odpowiedzialny_za_stan_techniczny"], "Serwis X")

    def test_osm_without_name_and_owner_gives_notes(self):
        res = run(row("osm1", "osm-openaedmap", wynik_sprawdzenia="potwierdzam", data_sprawdzenia="2026-11-20"))
        msgs = " ".join(p["komunikat"] for p in res["problemy"])
        self.assertIn("nazwa_obiektu_poprawiona", msgs)
        self.assertIn("dysponent_poprawiony", msgs)
        self.assertIn("wpisano dystrybutora", msgs)
        self.assertEqual(res["potwierdzone"][0]["lokalizacje_potwierdzil"], "Centrum Ratownictwa X")
        self.assertEqual(res["potwierdzone"][0]["nazwa_obiektu"], "")

    def test_other_place_requires_new_coordinates(self):
        same = run(row("osm1", "osm-openaedmap", wynik_sprawdzenia="inne_miejsce", data_sprawdzenia="2026-11-20"))
        self.assertEqual(same["potwierdzone"], [])
        self.assertIn("współrzędne bez zmian", same["problemy"][0]["komunikat"])
        moved = run(row("osm1", "osm-openaedmap", wynik_sprawdzenia="inne_miejsce", data_sprawdzenia="2026-11-20",
                        szerokosc_geo="49,7503", nazwa_obiektu_poprawiona="Hala", dysponent_poprawiony="MOSiR"))
        rec = moved["potwierdzone"][0]
        self.assertEqual(rec["szerokosc_geo"], "49.750300")  # przecinek dziesiętny z Excela
        self.assertEqual(rec["gmina"], "")  # do wyliczenia od nowa (CLI: gminy.enrich)
        self.assertTrue(rec["_inne_miejsce"])

    def test_missing_device_and_unchecked(self):
        res = run(row("osm1", "osm-openaedmap", wynik_sprawdzenia="brak_urzadzenia", data_sprawdzenia="2026-11-19",
                      uwagi_dystrybutora="zdjęty"),
                  row("inst1", "danegovpl-krosno"))
        self.assertEqual(res["potwierdzone"], [])
        self.assertEqual(res["do_usuniecia"][0]["id_zrodlowe"], "src-osm1")
        self.assertEqual(res["pominiete"], ["inst1"])
        self.assertEqual(res["problemy"], [])  # OSM: data powiadomienia niepotrzebna

    def test_institution_missing_device_and_notification(self):
        # Review #37: bez daty powiadomienia – uwaga „najpierw poinformuj dysponenta”, z datą – bez uwag.
        bez = run(row("inst1", "danegovpl-krosno", wynik_sprawdzenia="brak_urzadzenia", data_sprawdzenia="2026-11-19"))
        self.assertEqual(bez["do_usuniecia"][0]["poinformowano_dysponenta"], "")
        self.assertIn("najpierw poinformuj dysponenta", bez["problemy"][0]["komunikat"])
        z = run(row("inst1", "danegovpl-krosno", wynik_sprawdzenia="brak_urzadzenia", data_sprawdzenia="2026-11-19",
                    poinformowano_dysponenta="20.11.2026"))
        self.assertEqual(z["do_usuniecia"][0]["poinformowano_dysponenta"], "2026-11-20")
        self.assertEqual(z["problemy"], [])
        # Review #42, pkt 4: literówka w dacie nie wyrzuca zgłoszenia – zostaje z pustą datą.
        for bad in ("2062-01-01", "tak", "20.11", "2025-11-20"):  # ostatnia: wcześniej niż data_sprawdzenia
            zla = run(row("inst1", "danegovpl-krosno", wynik_sprawdzenia="brak_urzadzenia",
                          data_sprawdzenia="2026-11-19", poinformowano_dysponenta=bad))
            self.assertEqual(zla["do_usuniecia"][0]["poinformowano_dysponenta"], "", bad)
            self.assertIn("poinformowano_dysponenta", zla["problemy"][0]["komunikat"])
        osm = run(row("osm1", "osm-openaedmap", wynik_sprawdzenia="brak_urzadzenia", data_sprawdzenia="2026-11-19",
                      poinformowano_dysponenta="tak"))
        self.assertEqual(len(osm["do_usuniecia"]), 1)  # wpis OSM i tak znika

    def test_old_list_without_new_columns(self):
        # Review #42, pkt 1: listy rozesłane przed #36/#42 nie mają nazwa_obiektu_poprawiona
        # ani poinformowano_dysponenta – muszą się wczytać.
        old_cols = [c for c in distributor.KOLUMNY if c not in di.OPTIONAL_COLUMNS]
        path = Path(tempfile.mkdtemp()) / "stara.csv"
        with path.open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=old_cols)
            writer.writeheader()
            writer.writerow({k: "" for k in old_cols} | {"id_aed": "inst1", "zrodlo": "danegovpl-krosno"})
        rows = di.read_worklist(path)
        self.assertEqual((rows[0]["poinformowano_dysponenta"], rows[0]["nazwa_obiektu_poprawiona"]), ("", ""))

    def test_distributor_osm_copy_is_not_institution(self):
        # Review #42, pkt 5: jedna reguła w imporcie i w build.
        sources = {"danegovpl-krosno"}
        self.assertTrue(di.is_institution("danegovpl-krosno", sources))
        self.assertTrue(di.is_institution("danegovpl-krosno;dystrybutor", sources))
        self.assertFalse(di.is_institution("dystrybutor", sources))
        self.assertFalse(di.is_institution("osm-openaedmap", sources))

    def test_merge_with_previous_import(self):
        # Review #42, pkt 2: rekord usunięty po powiadomieniu (już nie na liście) nie może wrócić,
        # a pusta data w nowym wczytaniu nie kasuje starej.
        old = [{"id_aed": "gmina-usunieta", "poinformowano_dysponenta": "2026-11-20"},
               {"id_aed": "zgloszony", "poinformowano_dysponenta": "2026-11-20"},
               {"id_aed": "znaleziony", "poinformowano_dysponenta": ""}]
        new = [{"id_aed": "zgloszony", "poinformowano_dysponenta": ""}]
        merged = di.merge_registered(old, new, reported={"zgloszony", "znaleziony"})
        by_id = {r["id_aed"]: r for r in merged}
        self.assertIn("gmina-usunieta", by_id)  # nowe wczytanie o nim nie mówi – zostaje
        self.assertEqual(by_id["zgloszony"]["poinformowano_dysponenta"], "2026-11-20")
        self.assertNotIn("znaleziony", by_id)  # w nowym wczytaniu potwierdzony – już nie „brak”

    def test_invalid_rows(self):
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

    def test_repeated_aed(self):
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


class TestExcelFile(unittest.TestCase):
    def write(self, text: str, encoding: str) -> Path:
        path = Path(tempfile.mkdtemp()) / "lista.csv"
        path.write_bytes(text.encode(encoding))
        return path

    def test_semicolon_cp1250_and_apostrophe(self):
        header = ";".join(distributor.KOLUMNY)
        values = {k: "" for k in distributor.KOLUMNY}
        values.update(id_aed="inst1", zrodlo="danegovpl-krosno", nazwa_obiektu="'-Rynek", uwagi_dystrybutora="Żółw")
        path = self.write(header + "\n" + ";".join(values[k] for k in distributor.KOLUMNY) + "\n", "cp1250")
        rows = di.read_worklist(path)
        self.assertEqual(rows[0]["uwagi_dystrybutora"], "Żółw")
        self.assertEqual(rows[0]["nazwa_obiektu"], "-Rynek")  # apostrof z excel_safe() zdjęty

    def test_file_with_other_columns(self):
        with self.assertRaises(di.DistributorImportError):
            di.read_worklist(self.write("a,b\n1,2\n", "utf-8"))

    def test_write_result(self):
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
