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

    def test_rekordy_i_wspolrzedne(self):
        self.assertEqual(len(self.recs), 4)
        first = self.recs[0]
        self.assertEqual(first["id_zrodlowe"], "1")
        self.assertEqual((first["szerokosc_geo"], first["dlugosc_geo"]), ("49.718809", "21.720344"))
        self.assertEqual(first["_uwagi"], [])

    def test_adres_rozbity_na_pola(self):
        rec = self.recs[1]
        self.assertEqual(rec["ulica"], "Stanisława Wyspiańskiego")
        self.assertEqual(rec["numer_budynku"], "20")
        self.assertEqual(rec["kod_pocztowy"], "38-400")
        self.assertEqual(rec["miejscowosc"], "Krosno")
        self.assertEqual(self.recs[0]["numer_budynku"], "")  # „ul. Jasna, 38-400 Krosno”

    def test_nazwa_obiektu_bez_podwojnych_spacji(self):
        self.assertEqual(self.recs[0]["nazwa_obiektu"], "Zespół Krytych Pływalni")


class TestMarki(unittest.TestCase):
    """Marki: każdy wiersz w cudzysłowie, współrzędne odwrotnie niż w nagłówku."""

    def setUp(self):
        self.recs = adapter("danegovpl-marki").records(FIXTURES / "marki.csv")

    def test_cudzyslow_wokol_wiersza(self):
        self.assertEqual(len(self.recs), 4)
        self.assertEqual(self.recs[1]["nazwa_obiektu"], "Szkoła Podstawowa nr 1")

    def test_zamienione_wspolrzedne_naprawione_i_oznaczone(self):
        rec = self.recs[0]
        self.assertTrue(in_poland(float(rec["szerokosc_geo"]), float(rec["dlugosc_geo"])))
        self.assertEqual(rec["szerokosc_geo"], "52.326697")
        self.assertIn("współrzędne zamienione miejscami w źródle", rec["_uwagi"])

    def test_adres_z_podwojna_kropka(self):
        rec = self.recs[0]  # „Al.. Piłsudskiego 95, 05-270 Marki”
        self.assertEqual((rec["ulica"], rec["numer_budynku"]), ("Piłsudskiego", "95"))


class TestPrzemysl(unittest.TestCase):
    def setUp(self):
        self.recs = adapter("danegovpl-przemysl").records(FIXTURES / "przemysl.geojson")

    def test_nazwa_bez_prefiksu(self):
        self.assertEqual(self.recs[0]["nazwa_obiektu"], "ADM Centrum")

    def test_nazwa_bez_prefiksu_z_myslnikiem(self):
        # W Przemyślu część nazw ma postać „Defibrylator (AED7646) - Rynek 1”; bez tego
        # nazwa zaczynała się od „- ”, czyli od znaku formuły w Excelu.
        from ingest.adapters.danegovpl import _NAME_PREFIX
        for raw, name in (("Defibrylator (AED 9481) - Targowisko Zielony Rynek", "Targowisko Zielony Rynek"),
                          ("Defibrylator (AED7646) – Rynek 1", "Rynek 1"),
                          ("Defibrylator we Wsi", "Wsi"),
                          ("Wiata - przystanek", "Wiata - przystanek")):
            self.assertEqual(_NAME_PREFIX.sub("", raw).strip(), name)

    def test_pola_adresowe_i_kontakt(self):
        rec = self.recs[2]
        self.assertEqual(rec["kod_pocztowy"], "37-700")
        self.assertEqual(rec["numer_budynku"], "1")
        self.assertEqual(rec["telefon_kontaktowy"], "+48166779500")
        self.assertTrue(rec["zdjecie_url"].startswith("https://"))


class TestWspolne(unittest.TestCase):
    def test_komplet_pol_i_metadane(self):
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

    def test_stabilne_id_aed(self):
        a = adapter("danegovpl-krosno").records(FIXTURES / "krosno.csv")
        b = adapter("danegovpl-krosno").records(FIXTURES / "krosno.csv")
        self.assertEqual([r["id_aed"] for r in a], [r["id_aed"] for r in b])
        self.assertEqual(len({r["id_aed"] for r in a}), len(a))


if __name__ == "__main__":
    unittest.main()
