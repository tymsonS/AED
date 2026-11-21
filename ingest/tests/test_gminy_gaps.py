"""Testy przypisania do gmin i mapy luk na syntetycznych granicach (bez sieci)."""

import unittest
from datetime import date

from ingest import gaps, gminy
from ingest.fields import empty_record

# Dwie sąsiednie „gminy” – kwadraty 0,1° × 0,1°; druga z dziurą (inna gmina w środku).
GMINY = [
    {"teryt": "1861011", "nazwa": "Krosno", "powierzchnia_km2": 80.0,
     "polygons": [[[[21.7, 49.7], [21.8, 49.7], [21.8, 49.8], [21.7, 49.8], [21.7, 49.7]]]]},
    {"teryt": "1434021", "nazwa": "Marki", "powierzchnia_km2": 30.0,
     "polygons": [[[[21.8, 49.7], [21.9, 49.7], [21.9, 49.8], [21.8, 49.8], [21.8, 49.7]],
                   [[21.84, 49.74], [21.86, 49.74], [21.86, 49.76], [21.84, 49.76], [21.84, 49.74]]]]},
    {"teryt": "1801011", "nazwa": "Pusta", "powierzchnia_km2": 10.0,
     "polygons": [[[[22.0, 50.0], [22.1, 50.0], [22.1, 50.1], [22.0, 50.1], [22.0, 50.0]]]]},
]
TRUST = {"danegovpl-krosno": 1, "osm-openaedmap": 3}


def aed(lat, lon, zrodlo="osm-openaedmap", **kw):
    rec = empty_record()
    rec.update(szerokosc_geo=str(lat), dlugosc_geo=str(lon), zrodlo=zrodlo, dysponent_nazwa="",
               data_weryfikacji="", dostep="", dostepny_24h="nieznane", _uwagi=[])
    rec.update(kw)
    return rec


class TestGminy(unittest.TestCase):
    def setUp(self):
        self.index = gminy.GminaIndex(GMINY)

    def test_punkt_w_gminie(self):
        self.assertEqual(self.index.find(21.75, 49.75)["teryt"], "1861011")
        self.assertEqual(self.index.find(21.88, 49.71)["teryt"], "1434021")

    def test_dziura_w_gminie(self):
        self.assertIsNone(self.index.find(21.85, 49.75))

    def test_szczelina_przy_granicy(self):
        self.assertEqual(self.index.find(21.69985, 49.75)["teryt"], "1861011")  # ok. 10 m poza granicą

    def test_poza_polska(self):
        self.assertIsNone(self.index.find(10.0, 50.0))

    def test_enrich_wojewodztwo(self):
        recs = [aed(49.75, 21.75)]
        self.assertEqual(gminy.enrich(recs, self.index), 1)
        self.assertEqual((recs[0]["kod_teryt_gminy"], recs[0]["gmina"], recs[0]["wojewodztwo"]),
                         ("1861011", "Krosno", "podkarpackie"))

    def test_upraszczanie_zamknietego_pierscienia(self):
        ring = [[0, 0], [1, 0], [1, 1], [0.5, 1.00001], [0, 1], [0, 0]]
        self.assertEqual(gminy.simplify(ring, 0.001), [[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]])

    def test_kolejnosc_wspolrzednych_gml(self):
        self.assertEqual(gminy._poslist_lonlat("49.7 21.7 49.8 21.8"), [[21.7, 49.7], [21.8, 49.8]])


class TestMapaLuk(unittest.TestCase):
    def setUp(self):
        index = gminy.GminaIndex(GMINY)
        self.recs = [
            aed(49.75, 21.75, "danegovpl-krosno", dostep="publiczny", dostepny_24h="tak"),
            aed(49.75020, 21.75020),                      # ok. 27 m od zweryfikowanego – ten sam AED
            aed(49.72, 21.72, dysponent_nazwa="Szkoła"),  # osobny, niezweryfikowany
            aed(49.71, 21.88, data_weryfikacji="2026-06-01"),
            aed(49.71, 21.89, "danegovpl-krosno"),        # dysponent z Krosna, punkt w Markach
        ]
        gminy.enrich(self.recs, index)
        for rec in gaps.outside_publisher_area(self.recs, {"danegovpl-krosno": "1861011"}):
            rec["_uwagi"].append(f"{gaps.OUTSIDE_NOTE}: test")
        rows = gaps.build_gaps(self.recs, GMINY, TRUST, {"1861011": "danegovpl-krosno"}, date(2026, 11, 21))
        self.rows = {r["gmina"]: r for r in rows}

    def test_gmina_publikujaca(self):
        r = self.rows["Krosno"]
        self.assertEqual(r["status"], gaps.STATUS_PUBLIKUJE)
        self.assertEqual((r["aed_zweryfikowane"], r["aed_niezweryfikowane"]), (1, 1))
        self.assertEqual(r["osm_potwierdzone_przez_zrodlo_publiczne"], 1)
        self.assertEqual(r["niezweryfikowane_z_dysponentem"], 1)
        self.assertEqual(r["publicznie_24h"], 1)

    def test_rekord_poza_obszarem_dysponenta_nie_jest_zweryfikowany(self):
        r = self.rows["Marki"]
        self.assertEqual(r["aed_zweryfikowane"], 0)
        self.assertEqual(r["status"], gaps.STATUS_TYLKO_SPOLECZNE)
        self.assertEqual(r["niezweryfikowane_sprawdzone_12_mies"], 1)

    def test_gmina_bez_aed(self):
        self.assertEqual(self.rows["Pusta"]["status"], gaps.STATUS_BRAK)

    def test_podsumowanie(self):
        s = gaps.summary(list(self.rows.values()))
        self.assertEqual(s["gminy"], 3)
        self.assertEqual(s["gminy_wg_statusu"][gaps.STATUS_BRAK], 1)
        self.assertEqual(s["aed_zweryfikowane"], 1)


if __name__ == "__main__":
    unittest.main()
