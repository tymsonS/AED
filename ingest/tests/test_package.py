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


if __name__ == "__main__":
    unittest.main()
