"""Testy adaptera dane.gov.pl na próbkach prawdziwych zbiorów (bez sieci)."""

import tempfile
import unittest
from pathlib import Path

from ingest.adapters.danegovpl import DaneGovPlAdapter
from ingest.cli import load_sources
from ingest.fields import field_names
from ingest.normalize import in_poland

FIXTURES = Path(__file__).parent / "fixtures"


def adapter(source_id: str) -> DaneGovPlAdapter:
    source = next(s for s in load_sources() if s["id"] == source_id)
    return DaneGovPlAdapter(source, Path(tempfile.mkdtemp()))


class TestKrosno(unittest.TestCase):
    def setUp(self):
        self.recs = adapter("danegovpl-krosno").records(FIXTURES / "krosno.csv")

    def test_records_and_coordinates(self):
        self.assertEqual(len(self.recs), 4)
        first = self.recs[0]
        self.assertEqual(first["id_zrodlowe"], "1")
        self.assertEqual((first["szerokosc_geo"], first["dlugosc_geo"]), ("49.718809", "21.720344"))
        self.assertEqual(first["_uwagi"], [])

    def test_address_split_into_fields(self):
        rec = self.recs[1]
        self.assertEqual(rec["ulica"], "Stanisława Wyspiańskiego")
        self.assertEqual(rec["numer_budynku"], "20")
        self.assertEqual(rec["kod_pocztowy"], "38-400")
        self.assertEqual(rec["miejscowosc"], "Krosno")
        self.assertEqual(self.recs[0]["numer_budynku"], "")  # „ul. Jasna, 38-400 Krosno”

    def test_name_without_double_spaces(self):
        self.assertEqual(self.recs[0]["nazwa_obiektu"], "Zespół Krytych Pływalni")


class TestMarki(unittest.TestCase):
    """Marki: każdy wiersz w cudzysłowie, współrzędne odwrotnie niż w nagłówku."""

    def setUp(self):
        self.recs = adapter("danegovpl-marki").records(FIXTURES / "marki.csv")

    def test_quotes_around_row(self):
        self.assertEqual(len(self.recs), 4)
        self.assertEqual(self.recs[1]["nazwa_obiektu"], "Szkoła Podstawowa nr 1")

    def test_swapped_coordinates_fixed_and_flagged(self):
        rec = self.recs[0]
        self.assertTrue(in_poland(float(rec["szerokosc_geo"]), float(rec["dlugosc_geo"])))
        self.assertEqual(rec["szerokosc_geo"], "52.326697")
        self.assertIn("współrzędne zamienione miejscami w źródle", rec["_uwagi"])

    def test_address_with_double_dot(self):
        rec = self.recs[0]  # „Al.. Piłsudskiego 95, 05-270 Marki”
        self.assertEqual((rec["ulica"], rec["numer_budynku"]), ("Piłsudskiego", "95"))


class TestPrzemysl(unittest.TestCase):
    def setUp(self):
        self.recs = adapter("danegovpl-przemysl").records(FIXTURES / "przemysl.geojson")

    def test_name_without_prefix(self):
        self.assertEqual(self.recs[0]["nazwa_obiektu"], "ADM Centrum")

    def test_name_without_dash_prefix(self):
        # W Przemyślu część nazw ma postać „Defibrylator (AED7646) - Rynek 1”; bez tego
        # nazwa zaczynała się od „- ”, czyli od znaku formuły w Excelu.
        from ingest.adapters.danegovpl import _NAME_PREFIX
        for raw, name in (("Defibrylator (AED 9481) - Targowisko Zielony Rynek", "Targowisko Zielony Rynek"),
                          ("Defibrylator (AED7646) – Rynek 1", "Rynek 1"),
                          ("Defibrylator we Wsi", "Wsi"),
                          ("Wiata - przystanek", "Wiata - przystanek")):
            self.assertEqual(_NAME_PREFIX.sub("", raw).strip(), name)

    def test_address_fields_and_contact(self):
        rec = self.recs[2]
        self.assertEqual(rec["kod_pocztowy"], "37-700")
        self.assertEqual(rec["numer_budynku"], "1")
        self.assertEqual(rec["telefon_kontaktowy"], "+48166779500")
        # W Przemyślu każdy AED ma ten sam plik (ikona „AED”), więc zdjęcie jest pomijane (#47).
        self.assertEqual(rec["zdjecie_url"], "")
        self.assertTrue(any("zdjecie_url pominięte" in u for u in rec["_uwagi"]))


class TestSharedPhotos(unittest.TestCase):
    def test_photo_key_ignores_cms_slug_only(self):
        from ingest.adapters.base import photo_key
        a = "https://przemysl.skycms.com.pl/download/156869/defibrylator-aed-9485-w-adm-centrum"
        b = "https://przemysl.skycms.com.pl/download/156869/cokolwiek"
        self.assertEqual(photo_key(a), photo_key(b))
        # Pliki z rozszerzeniem i parametry zapytania to różne zdjęcia – bez zmian.
        self.assertNotEqual(photo_key("https://x.pl/wp-content/uploads/2026/03/a.jpg"),
                            photo_key("https://x.pl/wp-content/uploads/2026/03/b.jpg"))
        self.assertNotEqual(photo_key("https://cloud-b.edupage.org/cloud?z=1"),
                            photo_key("https://cloud-b.edupage.org/cloud?z=2"))
        self.assertNotEqual(photo_key("https://x.pl/download/1/a"), photo_key("https://x.pl/download/2/a"))
        # Review #49: sama liczba na końcu to numer zdjęcia.
        self.assertNotEqual(photo_key("https://x.pl/galeria/2024/5678"), photo_key("https://x.pl/galeria/2024/5679"))

    def rec(self, url, lat, lon=21.75):
        return {"zdjecie_url": url, "szerokosc_geo": str(lat), "dlugosc_geo": str(lon), "_uwagi": []}

    def test_icon_spread_over_city_dropped(self):
        from ingest.adapters.base import drop_shared_photos
        recs = [self.rec(f"https://x.pl/download/7/aed-{i}", 49.70 + i * 0.01) for i in range(3)]  # ok. 2 km
        out = drop_shared_photos(recs)
        self.assertEqual([r["zdjecie_url"] for r in out], ["", "", ""])
        self.assertIn("różnych miejscach", out[0]["_uwagi"][0])

    def test_same_photo_for_neighbouring_aeds_kept(self):
        from ingest.adapters.base import drop_shared_photos
        url = "https://openaedmap.org/api/v1/photos/view/abc.webp"
        recs = [self.rec(url, 49.7000), self.rec(url, 49.7003), self.rec(url, 49.7006)]  # ok. 70 m
        self.assertEqual([r["zdjecie_url"] for r in drop_shared_photos(recs)], [url] * 3)

    def test_provider_file_and_whole_source(self):
        """Review #49: reguła działa w package --plik / plik-dostawcy i w obrębie całego źródła."""
        import csv
        import tempfile
        from unittest import mock

        from ingest import cli, package
        from ingest.fields import field_names

        def write(path, lats):
            with path.open("w", encoding="utf-8", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=list(field_names()))
                w.writeheader()
                for i, lat in enumerate(lats):
                    w.writerow({k: "" for k in field_names()} | {
                        "zrodlo": "plik-dostawcy", "id_zrodlowe": f"{path.stem}-{i}", "szerokosc_geo": str(lat),
                        "dlugosc_geo": "21.75", "zdjecie_url": f"https://gmina.pl/download/9/aed-{path.stem}-{i}"})

        tmp = Path(tempfile.mkdtemp())
        one = tmp / "jeden.csv"
        write(one, [49.70, 49.72, 49.74])  # jeden plik, ikona przy 3 AED
        self.assertEqual({r["zdjecie_url"] for r in package.read_records_csv(one, "plik-dostawcy")}, {""})
        raw = tmp / "raw" / "plik-dostawcy"
        raw.mkdir(parents=True)
        write(raw / "resource-a.csv", [49.70, 49.72])  # po 2 AED w pliku – razem 4 w źródle
        write(raw / "resource-b.csv", [49.74, 49.76])
        with mock.patch.object(cli, "DATA", tmp), mock.patch.object(cli, "GMINY", tmp / "brak.json"):
            recs = cli.load_records("plik-dostawcy")
        self.assertEqual(len(recs), 4)
        self.assertEqual({r["zdjecie_url"] for r in recs}, {""})

    def test_two_uses_kept(self):
        from ingest.adapters.base import drop_shared_photos
        recs = [self.rec("https://x.pl/download/8/a", 49.7), self.rec("https://x.pl/download/8/b", 50.7)]
        self.assertEqual([r["zdjecie_url"] for r in drop_shared_photos(recs)],
                         ["https://x.pl/download/8/a", "https://x.pl/download/8/b"])


class TestCommon(unittest.TestCase):
    def test_all_fields_and_metadata(self):
        for sid, fx in (("danegovpl-krosno", "krosno.csv"), ("danegovpl-przemysl", "przemysl.geojson")):
            for rec in adapter(sid).records(FIXTURES / fx):
                self.assertTrue(set(field_names()) <= set(rec))
                self.assertEqual(rec["zrodlo"], sid)
                self.assertEqual(rec["godziny_dostepnosci"], "nieznane")
                self.assertEqual(rec["dostepny_24h"], "nieznane")
                self.assertEqual(rec["dostep"], "nieznany")
                # Bez wpisu w sources.toml nie twierdzimy, że ktoś potwierdził lokalizację.
                self.assertEqual(rec["lokalizacje_potwierdzil"], "")
                self.assertEqual(rec["odpowiedzialny_za_stan_techniczny"], "")

    def test_stable_id_aed(self):
        a = adapter("danegovpl-krosno").records(FIXTURES / "krosno.csv")
        b = adapter("danegovpl-krosno").records(FIXTURES / "krosno.csv")
        self.assertEqual([r["id_aed"] for r in a], [r["id_aed"] for r in b])
        self.assertEqual(len({r["id_aed"] for r in a}), len(a))


if __name__ == "__main__":
    unittest.main()
