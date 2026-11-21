"""Testy statystyk do prezentacji (bez sieci)."""

import unittest
from datetime import date

from ingest import gaps, stats
from ingest.tests.test_gminy_gaps import GMINY, TRUST, aed

TODAY = date(2026, 11, 21)
SOURCES = [
    {"id": "danegovpl-krosno", "dysponent": "Urząd Miasta Krosna", "poziom_zaufania": 1, "teryt": "1861011"},
    {"id": "osm-openaedmap", "dysponent": "OSM", "poziom_zaufania": 3},
]


class TestStatystyki(unittest.TestCase):
    def setUp(self):
        self.records = [
            aed(49.75, 21.75, zrodlo="danegovpl-krosno", id_aed="v1", dysponent_nazwa="UM Krosna",
                miejscowosc="Krosno", data_weryfikacji="2025-01-01", dostep="nieznany",
                godziny_dostepnosci="nieznane"),
            aed(49.7502, 21.75, id_aed="dup"),  # ten sam AED co v1
            aed(49.76, 21.75, id_aed="o1", dostep="publiczny", dostepny_24h="tak",
                godziny_dostepnosci="24/7", data_weryfikacji="2026-06-01", dysponent_nazwa="OSP"),
            aed(49.75, 21.85, id_aed="o2", dostep="prywatny"),
        ]
        for r in self.records:
            r["wojewodztwo"] = "podkarpackie"
        st = gaps.verification(self.records, TRUST)
        rows = gaps.build_gaps(self._with_teryt(), GMINY, TRUST, {"1861011": "danegovpl-krosno"}, TODAY)
        report = {"rekordy": 4, "rekordy_z_bledami": 2, "bledy": 2, "ostrzezenia": 2,
                  "problemy_wg_pola": {"dostep": 2, "dysponent_regon": 1},
                  "problemy": [{"pole": "dostep", "poziom": "blad"}, {"pole": "dostep", "poziom": "blad"},
                               {"pole": "dysponent_regon", "poziom": "ostrzezenie"},
                               {"pole": "", "poziom": "ostrzezenie"}]}
        self.s = stats.compute(self.records, st, SOURCES, rows, report, TODAY)

    def _with_teryt(self):
        for r, t in zip(self.records, ("1861011", "1861011", "1861011", "1434021")):
            r["kod_teryt_gminy"] = t
        return self.records

    def test_urzadzenia_a_wpisy(self):
        self.assertEqual(self.s["wpisy"], 4)
        self.assertEqual(self.s["aed"], 3)  # duplikat OSM liczy się raz
        self.assertEqual(self.s["duplikaty_osm_pominiete"], 1)
        self.assertEqual((self.s["aed_zweryfikowane"], self.s["aed_niezweryfikowane"]), (1, 2))

    def test_jakosc(self):
        q = self.s["jakosc"]
        self.assertEqual(q["wszystkie"]["publicznie dostępne 24/7"]["aed"], 1)
        self.assertEqual(q["wszystkie"]["sprawdzone w ostatnich 12 mies."]["aed"], 1)
        # „nieznany” / „nieznane” to brak informacji, nie informacja.
        self.assertEqual(q["zweryfikowane"]["z rodzajem dostępu"]["procent"], 0.0)
        self.assertEqual(q["zweryfikowane"]["z godzinami dostępności"]["procent"], 0.0)
        self.assertEqual(q["niezweryfikowane"]["ze wskazanym dysponentem"]["procent"], 50.0)

    def test_pokrycie(self):
        p = self.s["pokrycie"]
        self.assertEqual((p["gminy"], p["gminy_z_aed"], p["gminy_publikujace"]), (3, 2, 1))
        self.assertEqual(p["gminy_z_aed_bez_zadnego_dysponenta"], 1)  # Marki: tylko o2 bez dysponenta
        self.assertEqual({w["wojewodztwo"] for w in p["wojewodztwa"]}, {"podkarpackie", "mazowieckie"})

    def test_markdown(self):
        md = stats.render_md(self.s)
        self.assertIn("**3 AED**", md)
        self.assertIn("| `dostep` | 2 |", md)
        self.assertIn("liczy **wpisy**", md)
        self.assertIn("ODbL", md)
        self.assertIn("data danych zasobu", md)

    def test_bledy_i_ostrzezenia_osobno(self):
        v = self.s["walidacja"]
        self.assertEqual(v["najczestsze_bledy"], {"dostep": 2})
        self.assertEqual(v["najczestsze_ostrzezenia"], {"dysponent_regon": 1, "(uwagi adaptera)": 1})

    def test_data_z_przyszlosci_nie_jest_swiezym_sprawdzeniem(self):
        self.records[2]["data_weryfikacji"] = "2062-06-01"
        st = gaps.verification(self.records, TRUST)
        s = stats.compute(self.records, st, SOURCES, today=TODAY)
        self.assertEqual(s["jakosc"]["wszystkie"]["sprawdzone w ostatnich 12 mies."]["aed"], 0)

    def test_liczby_po_polsku(self):
        self.assertEqual(stats._n(18304), "18 304")
        self.assertEqual(stats._n(32.9), "32,9")
        forms = ("błąd", "błędy", "błędów")
        self.assertEqual([stats._plural(n, *forms) for n in (1, 2, 5, 12, 22, 36593, 19797)],
                         ["błąd", "błędy", "błędów", "błędów", "błędy", "błędy", "błędów"])


if __name__ == "__main__":
    unittest.main()
