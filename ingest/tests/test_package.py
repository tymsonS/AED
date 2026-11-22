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


class TestPackage(unittest.TestCase):
    def setUp(self):
        self.out = Path(tempfile.mkdtemp())
        self.paths = package.write_package(krosno_records(), meta(), self.out)

    def test_all_files_present(self):
        self.assertEqual(
            sorted(p.name for p in self.out.iterdir()),
            ["CZYTAJ-MNIE.txt", "aed.csv", "aed.geojson", "aed.md5", "aed.xml", "raport-walidacji.json"],
        )
        with self.paths["csv"].open(encoding="utf-8") as fh:
            self.assertEqual(len(list(csv.DictReader(fh))), 4)

    def test_md5_matches_xml(self):
        expected = hashlib.md5(self.paths["xml"].read_bytes()).hexdigest()
        self.assertEqual(self.paths["md5"].read_text(encoding="ascii").strip(), expected)

    def test_xml_schema_version_and_fields(self):
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

    def test_draft(self):
        xml = package.build_xml(meta(szkic=True))
        self.assertIn(b'status="draft"', xml)


class TestPortalConstraints(unittest.TestCase):
    def test_rejects_odbl(self):
        recs = krosno_records()
        recs[0]["licencja"] = "ODbL-1.0"
        with self.assertRaises(package.PackageError):
            package.write_package(recs, meta(), Path(tempfile.mkdtemp()))

    def test_https_only(self):
        with self.assertRaises(package.PackageError):
            meta(base_url="http://example.pl/").check()

    def test_license_outside_list(self):
        with self.assertRaises(package.PackageError):
            meta(licencja="ODbL").check()

    def test_teryt(self):
        with self.assertRaises(package.PackageError):
            meta(teryt="18610").check()


@unittest.skipUnless(XSD.exists() and importlib.util.find_spec("xmlschema"),
                     "brak XSD portalu lub biblioteki xmlschema (python -m ingest fetch-xsd)")
class TestPortalXsdCompliance(unittest.TestCase):
    def test_xml_matches_xsd(self):
        out = Path(tempfile.mkdtemp())
        paths = package.write_package(krosno_records(), meta(), out)
        self.assertEqual(package.validate_xml(paths["xml"], XSD), [])

    def test_invalid_xml_rejected(self):
        out = Path(tempfile.mkdtemp()) / "zly.xml"
        out.write_bytes(package.build_xml(meta()).replace(b"HEAL", b"ZDROWIE"))
        self.assertTrue(package.validate_xml(out, XSD))


class TestAedListFlag(unittest.TestCase):
    """--wykaz-aed: schemat 1.14 z portal/ i containsAedData przy aed.csv (wykaz zbiorczy AED, #76)."""

    def resources(self, xml: bytes, version: str) -> dict[str, ET.Element]:
        root = ET.fromstring(xml)
        self.assertEqual(root.tag, f"{{urn:otwarte-dane:harvester:{version}}}datasets")
        return {r.findtext("extIdent"): r for r in root.findall("dataset/resources/resource")}

    def test_default_stays_1_13_without_flag(self):
        res = self.resources(package.build_xml(meta()), "1.13")
        self.assertTrue(all(r.find("containsAedData") is None for r in res.values()))

    def test_flag_only_on_csv(self):
        res = self.resources(package.build_xml(meta(wykaz_aed=True)), "1.14")
        self.assertEqual(res["aed-1861011-csv"].findtext("containsAedData"), "true")
        self.assertEqual(res["aed-1861011-geojson"].findtext("containsAedData"), "false")

    def test_instructions_name_schema(self):
        self.assertIn("harvester:1.14", package._instructions(meta(wykaz_aed=True), 4))
        self.assertIn("--wykaz-aed", package._instructions(meta(), 4))

    def test_default_xsd_falls_back_to_portal(self):
        path = package.default_xsd_path("1.14", Path(tempfile.mkdtemp()))
        self.assertEqual(path, package.PORTAL_XSD_DIR / "xml_import_otwarte_dane_1_14.xsd")

    @unittest.skipUnless(importlib.util.find_spec("xmlschema")
                         and (package.PORTAL_XSD_DIR / "xml_import_otwarte_dane_1_14.xsd").exists(),
                         "brak biblioteki xmlschema albo XSD 1.14 w portal/")
    def test_xml_matches_portal_xsd_1_14(self):
        out = Path(tempfile.mkdtemp())
        paths = package.write_package(krosno_records(), meta(wykaz_aed=True), out)
        self.assertEqual(package.validate_xml(paths["xml"], package.PORTAL_XSD_DIR / "xml_import_otwarte_dane_1_14.xsd"), [])
        # Ten sam plik nie przejdzie jako 1.13 – dzisiejszy dane.gov.pl go nie przyjmie.
        self.assertTrue(package.validate_xml(paths["xml"], package.PORTAL_XSD_DIR / "xml_import_otwarte_dane_1_13.xsd"))


class TestPackageFromFile(unittest.TestCase):
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

    def test_reads_bom_file_and_filters_area(self):
        records = package.read_records_csv(self.write_csv(self.recs, encoding="utf-8-sig"))
        self.assertEqual(len(records), len(self.recs))
        self.assertEqual(records[0]["lokalizacje_potwierdzil"], "Centrum Ratownictwa X")
        self.assertEqual(records[0]["_uwagi"], [])
        inside, outside = package.filter_area(records, "1861011")
        self.assertEqual((len(inside), outside), (len(self.recs) - 2, 2))  # inna gmina i bez kodu
        self.assertEqual(len(package.filter_area(records, "18")[0]), len(self.recs) - 1)

    def test_package_from_file(self):
        records, _ = package.filter_area(package.read_records_csv(self.write_csv(self.recs)), "1861011")
        out = Path(tempfile.mkdtemp())
        paths = package.write_package(records, meta(), out)
        with paths["csv"].open(encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(len(rows), len(self.recs) - 2)
        self.assertEqual(rows[0]["metoda_weryfikacji"], "dystrybutor")

    def test_missing_columns(self):
        path = Path(tempfile.mkdtemp()) / "zly.csv"
        path.write_text("a,b\n1,2\n", encoding="utf-8")
        with self.assertRaises(package.PackageError):
            package.read_records_csv(path)

    def test_polish_excel_file(self):
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

    def test_empty_id_aed_like_municipality_template(self):
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

    def test_schema_example_gets_id_aed(self):
        example = Path(__file__).resolve().parents[2] / "schema" / "przyklad-aed.csv"
        if not example.exists():
            self.skipTest("brak schema/przyklad-aed.csv")
        rows = list(csv.DictReader(example.open(encoding="utf-8")))
        for r in rows:
            r["id_aed"] = ""
        got = package.read_records_csv(self.write_csv(rows), default_source="aed-x")
        self.assertTrue(all(r["id_aed"] for r in got))


    def test_odbl_from_file_rejected(self):
        records = package.read_records_csv(self.write_csv([dict(self.recs[0], licencja="ODbL-1.0")]))
        with self.assertRaises(package.PackageError):
            package.write_package(records, meta(), Path(tempfile.mkdtemp()))


def municipality_template(points, **kw):
    """Wiersze jak z szablonu XLSX gminy: puste id_aed, id_zrodlowe i zrodlo."""
    from ingest.fields import field_names
    rows = []
    for lat, lon in points:
        r = {k: "" for k in field_names()}
        r.update(szerokosc_geo=lat, dlugosc_geo=lon, nazwa_obiektu="Szkoła", dostep="publiczny",
                 godziny_dostepnosci="24/7", dostepny_24h="tak", status="aktywny", dysponent_nazwa="Gmina X",
                 data_weryfikacji="2026-11-20", licencja="CC-BY-4.0", data_aktualizacji="2026-11-21T13:00:00",
                 kod_teryt_gminy="1861011")
        r.update(kw)
        rows.append(r)
    return rows


class TestMunicipalityTemplateReview39(unittest.TestCase):
    """Trzecia runda review #39: prawdziwy szablon gminy bez id_zrodlowe i plik po Excelu."""

    def write(self, rows, encoding="utf-8", delimiter=","):
        path = Path(tempfile.mkdtemp()) / "gmina.csv"
        with path.open("w", encoding=encoding, newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0]), delimiter=delimiter)
            writer.writeheader()
            writer.writerows(rows)
        return path

    def test_template_without_source_id_no_errors(self):
        from ingest import validate
        rows = municipality_template([("49.6988", "21.7654"), ("49.7000", "21.7700"), ("49.7000", "21.7700")])
        recs = package.read_records_csv(self.write(rows), default_source=package.DEFAULT_FILE_SOURCE)
        self.assertEqual([r["id_zrodlowe"] for r in recs],
                         ["wsp-49.698800-21.765400", "wsp-49.700000-21.770000", "wsp-49.700000-21.770000-2"])
        self.assertEqual(len({r["id_aed"] for r in recs}), 3)  # dwa AED w jednym miejscu – różne id
        self.assertEqual({r["zrodlo"] for r in recs}, {"plik-dostawcy"})
        rep = validate.validate(recs)
        self.assertEqual(rep["rekordy_z_bledami"], 0, rep["problemy_wg_pola"])

    def test_id_aed_stable_after_excel_resave(self):
        a = package.read_records_csv(self.write(municipality_template([("49.6988", "21.7654")])), "plik-dostawcy")
        b = package.read_records_csv(self.write(municipality_template([("49.69880", "21.76540")])), "plik-dostawcy")
        self.assertEqual(a[0]["id_aed"], b[0]["id_aed"])

    def test_default_source_in_registry(self):
        self.assertIn(package.DEFAULT_FILE_SOURCE, {s["id"] for s in load_sources()})

    def test_excel_leading_zeros(self):
        rows = municipality_template([("51,1079", "17,0385")], kod_teryt_gminy="264011", dysponent_regon="12345678",
                             dysponent_nip="525000001", telefon_kontaktowy="48221234567",
                             data_aktualizacji="21.11.2026 12:00")
        rec = package.read_records_csv(self.write(rows, encoding="cp1250", delimiter=";"), "plik-dostawcy")[0]
        self.assertEqual(rec["kod_teryt_gminy"], "0264011")  # Wrocław, dolnośląskie
        self.assertEqual(rec["dysponent_regon"], "012345678")
        self.assertEqual(rec["dysponent_nip"], "0525000001")
        self.assertEqual(rec["telefon_kontaktowy"], "+48221234567")
        self.assertEqual(rec["data_aktualizacji"], "2026-11-21T12:00:00")  # czas polski bez strefy (#61)
        self.assertEqual(package.filter_area([rec], "02")[1], 0)

    def test_distributor_signature_not_truncated(self):
        recs = krosno_records()
        long_name = "Centrum Ratownictwa " + "Bardzo Długa Nazwa Instytucji " * 40
        recs[0].update(metoda_weryfikacji="dystrybutor", lokalizacje_potwierdzil=long_name.strip())
        m = meta(gmina="Krosno " * 30)
        package.write_package(recs, m, Path(tempfile.mkdtemp()))
        root = ET.fromstring(package.build_xml(m))
        desc = root.find("dataset/description/polish").text
        self.assertLessEqual(len(desc), 1000)
        self.assertIn("potwierdził dystrybutor", desc)



class TestPolishTimeAndProviderSource(unittest.TestCase):
    """Drobne uwagi z review #39 po scaleniu: strefa czasowa i adapter plik-dostawcy."""

    def test_excel_datetime_is_polish_time_without_zone(self):
        # Godzina z Excela to już czas polski – bez przeliczania i bez strefy (#61),
        # niezależnie od strefy komputera (review #39).
        from ingest.csvio import parse_datetime
        self.assertEqual(parse_datetime("01.07.2026 12:00").isoformat(), "2026-07-01T12:00:00")
        self.assertEqual(parse_datetime("2026-11-21 12:00:05").isoformat(), "2026-11-21T12:00:05")

    def test_zoned_iso_converted_to_polish_time_without_zone(self):
        # #61: starsze pliki z „…Z” – przeliczone na czas polski bez strefy (zima +1 h, lato +2 h).
        from datetime import datetime, timezone

        from ingest.csvio import parse_datetime, warsaw_now
        self.assertEqual(parse_datetime("2026-11-21T12:00:00Z").isoformat(), "2026-11-21T13:00:00")
        self.assertEqual(parse_datetime("2026-07-01T12:00:00+00:00").isoformat(), "2026-07-01T14:00:00")
        self.assertEqual(parse_datetime("2026-07-01T14:00:00+02:00").isoformat(), "2026-07-01T14:00:00")
        # Review #63: bez sekund dostaje „:00”, poprawny zapis zostaje bez zmian (także z ułamkiem).
        from ingest.csvio import polish_datetime
        self.assertEqual(polish_datetime("2026-11-21T13:00"), "2026-11-21T13:00:00")
        self.assertEqual(polish_datetime("2026-11-21T13:00:00.123456"), "2026-11-21T13:00:00.123456")
        self.assertEqual(polish_datetime("nie data"), "nie data")
        self.assertEqual(polish_datetime(""), "")
        # Zmiana czasu w UE o 01:00 UTC: 29.03.2026 i 25.10.2026.
        self.assertEqual(warsaw_now(datetime(2026, 3, 29, 0, 59, tzinfo=timezone.utc)), "2026-03-29T01:59:00")
        self.assertEqual(warsaw_now(datetime(2026, 3, 29, 1, 0, tzinfo=timezone.utc)), "2026-03-29T03:00:00")
        self.assertEqual(warsaw_now(datetime(2026, 10, 25, 0, 59, tzinfo=timezone.utc)), "2026-10-25T02:59:00")
        self.assertEqual(warsaw_now(datetime(2026, 10, 25, 1, 0, tzinfo=timezone.utc)), "2026-10-25T02:00:00")

    def test_provider_file_adapter_reads_like_package_file(self):
        from ingest.adapters.wzorcowy_csv import WzorcowyCsvAdapter
        source = next(s for s in load_sources() if s["id"] == package.DEFAULT_FILE_SOURCE)
        root = Path(tempfile.mkdtemp())
        adapter = WzorcowyCsvAdapter(source, root)
        adapter.raw_dir.mkdir(parents=True)
        rows = municipality_template([("49,6988", "21,7654")], data_weryfikacji="20.11.2026")
        path = adapter.raw_dir / "resource-gmina.csv"
        with path.open("w", encoding="cp1250", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0]), delimiter=";")
            writer.writeheader()
            writer.writerows(rows)
        rec = adapter.records(path)[0]
        self.assertEqual(rec["zrodlo"], "plik-dostawcy")
        self.assertTrue(rec["id_aed"] and rec["id_zrodlowe"])
        self.assertEqual((rec["szerokosc_geo"], rec["data_weryfikacji"]), ("49.6988", "2026-11-20"))

    def test_provider_file_trust_level_is_2(self):
        source = next(s for s in load_sources() if s["id"] == package.DEFAULT_FILE_SOURCE)
        self.assertEqual(source["poziom_zaufania"], 2)  # decyzja 21.11 (sources.toml)


class TestCliPackageFromFile(unittest.TestCase):
    """CLI: kod wyjścia bez XSD i rekordy bez kod_teryt_gminy (review #39)."""

    def run_cli(self, rows, teryt="1861011", gminy_path=None):
        from unittest import mock

        from ingest import cli
        tmp = Path(tempfile.mkdtemp())
        path = tmp / "gmina.csv"
        with path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        argv = ["package", "--plik", str(path), "--teryt", teryt, "--gmina", "Krosno", "--dostawca", "Gmina X",
                "--base-url", "https://x.pl/aed/", "--xsd", str(tmp / "brak.xsd")]
        with mock.patch.object(cli, "DATA", tmp), mock.patch.object(cli, "GMINY", gminy_path or tmp / "brak.json"):
            try:
                cli.main(argv)
            except SystemExit as exc:
                return exc.code
        return 0

    def test_errors_without_xsd_exit_1(self):
        rows = municipality_template([("49.6988", "21.7654")], nazwa_obiektu="")
        self.assertIn("błędami walidacji", str(self.run_cli(rows)))

    def test_no_errors_without_xsd_exit_0(self):
        self.assertEqual(self.run_cli(municipality_template([("49.6988", "21.7654")])), 0)

    def test_missing_teryt_single_municipality_uses_arg(self):
        self.assertEqual(self.run_cli(municipality_template([("49.6988", "21.7654")], kod_teryt_gminy="")), 0)

    def test_missing_teryt_voivodeship_clear_error(self):
        code = self.run_cli(municipality_template([("49.6988", "21.7654")], kod_teryt_gminy=""), teryt="18")
        self.assertIn("bez kod_teryt_gminy", str(code))


class TestDatasetLicense(unittest.TestCase):
    """Review #39: licencja zbioru nie może być łagodniejsza niż licencja rekordów."""

    def test_matrix(self):
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

    def test_package_rejects_more_permissive_license(self):
        recs = krosno_records()
        recs[0]["licencja"] = "CC-BY-SA-4.0"
        with self.assertRaises(package.PackageError) as ctx:
            package.write_package(recs, meta(), Path(tempfile.mkdtemp()))
        self.assertIn("łagodniejsza", str(ctx.exception))
        package.write_package([recs[0]], meta(licencja="CC BY-SA 4.0"), Path(tempfile.mkdtemp()))

    def test_dataset_description_with_distributor(self):
        recs = krosno_records()
        recs[0].update(metoda_weryfikacji="dystrybutor", lokalizacje_potwierdzil="Centrum Ratownictwa X")
        paths = package.write_package(recs, meta(), Path(tempfile.mkdtemp()))
        xml = paths["xml"].read_text(encoding="utf-8")
        self.assertIn(f"Lokalizację 1 z {len(recs)} urządzeń potwierdził dystrybutor: Centrum Ratownictwa X.", xml)
        plain = package.write_package(krosno_records(), meta(), Path(tempfile.mkdtemp()))
        self.assertNotIn("dystrybutor:", plain["xml"].read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
