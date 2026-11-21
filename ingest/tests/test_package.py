"""Testy pakietu dostawcy (bez sieci).

Walidacja względem XSD portalu uruchamia się, gdy jest plik XSD (python -m ingest
fetch-xsd albo zmienna AED_XSD) i biblioteka xmlschema.
"""

import csv
import hashlib
import importlib.util
import os
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from ingest import package
from ingest.adapters.danegovpl import DaneGovPlAdapter
from ingest.cli import DATA, load_sources

FIXTURES = Path(__file__).parent / "fixtures"
XSD = Path(os.environ.get("AED_XSD", DATA / "xsd" / package.XSD_NAME))
NS = {"h": package.NAMESPACE}


def krosno_records() -> list[dict]:
    source = next(s for s in load_sources() if s["id"] == "danegovpl-krosno")
    return DaneGovPlAdapter(source, Path(tempfile.mkdtemp())).records(FIXTURES / "krosno.csv")


def meta(**kw) -> package.PackageMeta:
    base = dict(teryt="1861011", gmina="Krosno", dostawca="Urząd Miasta Krosna",
                base_url="https://example.krosno.pl/dane/aed")
    base.update(kw)
    return package.PackageMeta(**base)


class TestPakiet(unittest.TestCase):
    def setUp(self):
        self.out = Path(tempfile.mkdtemp())
        self.paths = package.write_package(krosno_records(), meta(), self.out)

    def test_komplet_plikow(self):
        self.assertEqual(
            sorted(p.name for p in self.out.iterdir()),
            ["CZYTAJ-MNIE.txt", "aed.csv", "aed.geojson", "aed.md5", "aed.xml", "raport-walidacji.json"],
        )
        with self.paths["csv"].open(encoding="utf-8") as fh:
            self.assertEqual(len(list(csv.DictReader(fh))), 4)

    def test_md5_zgodne_z_xml(self):
        expected = hashlib.md5(self.paths["xml"].read_bytes()).hexdigest()
        self.assertEqual(self.paths["md5"].read_text(encoding="ascii").strip(), expected)

    def test_xml_wersja_schematu_i_pola(self):
        root = ET.parse(self.paths["xml"]).getroot()
        self.assertEqual(root.tag, f"{{{package.NAMESPACE}}}datasets")
        ds = root.find("dataset")
        self.assertEqual(ds.get("status"), "published")
        self.assertEqual(ds.findtext("extIdent"), "aed-1861011")
        self.assertEqual(ds.findtext("categories/category"), "HEAL")
        self.assertEqual(ds.findtext("conditions/dbOrCopyrightedLicenseChosen"), "CC BY 4.0")
        urls = [r.findtext("url") for r in ds.findall("resources/resource")]
        self.assertEqual(urls, ["https://example.krosno.pl/dane/aed/aed.csv",
                                "https://example.krosno.pl/dane/aed/aed.geojson"])
        self.assertEqual(ds.findtext("resources/resource/regions/terytIdent"), "1861011")

    def test_szkic(self):
        xml = package.build_xml(meta(szkic=True))
        self.assertIn(b'status="draft"', xml)


class TestOgraniczeniaPortalu(unittest.TestCase):
    def test_odrzuca_odbl(self):
        recs = krosno_records()
        recs[0]["licencja"] = "ODbL-1.0"
        with self.assertRaises(package.PackageError):
            package.write_package(recs, meta(), Path(tempfile.mkdtemp()))

    def test_tylko_https(self):
        with self.assertRaises(package.PackageError):
            meta(base_url="http://example.pl/").check()

    def test_licencja_spoza_listy(self):
        with self.assertRaises(package.PackageError):
            meta(licencja="ODbL").check()

    def test_teryt(self):
        with self.assertRaises(package.PackageError):
            meta(teryt="18610").check()


@unittest.skipUnless(XSD.exists() and importlib.util.find_spec("xmlschema"),
                     "brak XSD portalu lub biblioteki xmlschema (python -m ingest fetch-xsd)")
class TestZgodnoscZXsdPortalu(unittest.TestCase):
    def test_xml_zgodny_z_xsd(self):
        out = Path(tempfile.mkdtemp())
        paths = package.write_package(krosno_records(), meta(), out)
        self.assertEqual(package.validate_xml(paths["xml"], XSD), [])

    def test_xml_z_bledem_odrzucony(self):
        out = Path(tempfile.mkdtemp()) / "zly.xml"
        out.write_bytes(package.build_xml(meta()).replace(b"HEAL", b"ZDROWIE"))
        self.assertTrue(package.validate_xml(out, XSD))


class TestPakietZPliku(unittest.TestCase):
    """Pakiet z CSV we wzorcowym zakresie, np. potwierdzone.csv od dystrybutora."""

    def write_csv(self, records, encoding="utf-8"):
        from ingest.fields import field_names
        path = Path(tempfile.mkdtemp()) / "potwierdzone.csv"
        with path.open("w", encoding=encoding, newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(field_names()), extrasaction="ignore")
            writer.writeheader()
            writer.writerows(records)
        return path

    def setUp(self):
        recs = krosno_records()
        for r, teryt in zip(recs, ["1861011"] * (len(recs) - 2) + ["1862011", ""]):
            r["kod_teryt_gminy"] = teryt
        recs[0].update(zrodlo="danegovpl-krosno;dystrybutor", metoda_weryfikacji="dystrybutor",
                       lokalizacje_potwierdzil="Centrum Ratownictwa X")
        self.recs = recs

    def test_czyta_plik_z_bom_i_filtruje_obszar(self):
        records = package.read_records_csv(self.write_csv(self.recs, encoding="utf-8-sig"))
        self.assertEqual(len(records), len(self.recs))
        self.assertEqual(records[0]["lokalizacje_potwierdzil"], "Centrum Ratownictwa X")
        self.assertEqual(records[0]["_uwagi"], [])
        inside, outside = package.filter_area(records, "1861011")
        self.assertEqual((len(inside), outside), (len(self.recs) - 2, 2))  # inna gmina i bez kodu
        self.assertEqual(len(package.filter_area(records, "18")[0]), len(self.recs) - 1)

    def test_pakiet_z_pliku(self):
        records, _ = package.filter_area(package.read_records_csv(self.write_csv(self.recs)), "1861011")
        out = Path(tempfile.mkdtemp())
        paths = package.write_package(records, meta(), out)
        with paths["csv"].open(encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(len(rows), len(self.recs) - 2)
        self.assertEqual(rows[0]["metoda_weryfikacji"], "dystrybutor")

    def test_brak_kolumn(self):
        path = Path(tempfile.mkdtemp()) / "zly.csv"
        path.write_text("a,b\n1,2\n", encoding="utf-8")
        with self.assertRaises(package.PackageError):
            package.read_records_csv(path)

    def test_plik_z_polskiego_excela(self):
        # Review #39: Windows-1250, średnik, DD.MM.RRRR i przecinek dziesiętny – jak lista dystrybutora.
        from ingest.fields import field_names
        rec = dict(self.recs[0], nazwa_obiektu="Pływalnia", data_weryfikacji="21.11.2026",
                   szerokosc_geo="49,6988", dlugosc_geo="21,7654")
        path = Path(tempfile.mkdtemp()) / "gmina.csv"
        with path.open("w", encoding="cp1250", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(field_names()), delimiter=";", extrasaction="ignore")
            writer.writeheader()
            writer.writerow(rec)
        got = package.read_records_csv(path)[0]
        self.assertEqual(got["nazwa_obiektu"], "Pływalnia")
        self.assertEqual(got["data_weryfikacji"], "2026-11-21")
        self.assertEqual((got["szerokosc_geo"], got["dlugosc_geo"]), ("49.6988", "21.7654"))

    def test_puste_id_aed_jak_w_szablonie_gminy(self):
        # Review #39: w szablonie XLSX id_aed jest puste, bo nadaje je system.
        from ingest import normalize
        rows = [dict(self.recs[0], id_aed="", id_zrodlowe="17"),
                dict(self.recs[1], id_aed="", zrodlo="", id_zrodlowe="18"),
                dict(self.recs[2], id_aed="", id_zrodlowe="")]
        got = package.read_records_csv(self.write_csv(rows), default_source="aed-1861011")
        self.assertEqual(got[0]["id_aed"], normalize.stable_id(rows[0]["zrodlo"], "17"))
        self.assertEqual((got[1]["zrodlo"], got[1]["id_aed"]), ("aed-1861011", normalize.stable_id("aed-1861011", "18")))
        self.assertTrue(got[2]["id_aed"])  # bez id_zrodlowe – klucz ze współrzędnych
        again = package.read_records_csv(self.write_csv(rows), default_source="aed-1861011")
        self.assertEqual([r["id_aed"] for r in got], [r["id_aed"] for r in again])  # stały między wczytaniami

    def test_przyklad_ze_schematu_ma_id_aed_w_pakiecie(self):
        example = Path(__file__).resolve().parents[2] / "schema" / "przyklad-aed.csv"
        if not example.exists():
            self.skipTest("brak schema/przyklad-aed.csv")
        rows = list(csv.DictReader(example.open(encoding="utf-8")))
        for r in rows:
            r["id_aed"] = ""
        got = package.read_records_csv(self.write_csv(rows), default_source="aed-x")
        self.assertTrue(all(r["id_aed"] for r in got))


    def test_odbl_z_pliku_odrzucony(self):
        records = package.read_records_csv(self.write_csv([dict(self.recs[0], licencja="ODbL-1.0")]))
        with self.assertRaises(package.PackageError):
            package.write_package(records, meta(), Path(tempfile.mkdtemp()))


class TestLicencjaZbioru(unittest.TestCase):
    """Review #39: licencja zbioru nie może być łagodniejsza niż licencja rekordów."""

    def test_macierz(self):
        fits = package.license_fits
        self.assertTrue(fits("CC0-1.0", "CC BY 4.0"))
        self.assertTrue(fits("CC0-1.0", "CC0 1.0"))
        self.assertTrue(fits("CC-BY-4.0", "CC BY 4.0"))
        self.assertTrue(fits("CC-BY-4.0", "CC BY-NC 4.0"))
        self.assertFalse(fits("CC-BY-4.0", "CC0 1.0"))
        self.assertFalse(fits("CC-BY-SA-4.0", "CC BY 4.0"))
        self.assertTrue(fits("CC-BY-SA-4.0", "CC BY-SA 4.0"))
        self.assertFalse(fits("CC-BY-SA-4.0", "CC BY-NC-SA 4.0"))  # SA: tylko ta sama licencja
        self.assertFalse(fits("CC-BY-NC-4.0", "CC BY 4.0"))
        self.assertFalse(fits("ODbL-1.0", "CC BY-SA 4.0"))

    def test_pakiet_odrzuca_lagodniejsza_licencje(self):
        recs = krosno_records()
        recs[0]["licencja"] = "CC-BY-SA-4.0"
        with self.assertRaises(package.PackageError) as ctx:
            package.write_package(recs, meta(), Path(tempfile.mkdtemp()))
        self.assertIn("łagodniejsza", str(ctx.exception))
        package.write_package([recs[0]], meta(licencja="CC BY-SA 4.0"), Path(tempfile.mkdtemp()))

    def test_opis_zbioru_z_dystrybutorem(self):
        recs = krosno_records()
        recs[0].update(metoda_weryfikacji="dystrybutor", lokalizacje_potwierdzil="Centrum Ratownictwa X")
        paths = package.write_package(recs, meta(), Path(tempfile.mkdtemp()))
        xml = paths["xml"].read_text(encoding="utf-8")
        self.assertIn(f"Lokalizację 1 z {len(recs)} urządzeń potwierdził dystrybutor: Centrum Ratownictwa X.", xml)
        plain = package.write_package(krosno_records(), meta(), Path(tempfile.mkdtemp()))
        self.assertNotIn("dystrybutor:", plain["xml"].read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
