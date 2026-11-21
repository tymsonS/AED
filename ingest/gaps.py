"""Mapa luk: stan danych o AED w każdej gminie.

Zweryfikowane = rekordy ze źródeł, za które odpowiada instytucja (poziom zaufania 1–2,
np. zbiory gmin na dane.gov.pl). Niezweryfikowane = dane społeczne (poziom 3, OSM).
Punkt OSM w promieniu 50 m od zweryfikowanego liczymy jako potwierdzony – to ten
sam AED, a nie drugi (typowy przypadek: dwa wpisy przy dwóch wejściach).
Wynik to lista adresatów kampanii „zweryfikuj swój AED”.
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, timedelta

from .gminy import WOJEWODZTWA

MATCH_RADIUS_M = 50

STATUS_PUBLIKUJE = "publikuje dane"
STATUS_CZESCIOWO = "część AED zweryfikowana"
STATUS_TYLKO_SPOLECZNE = "tylko dane niezweryfikowane"
STATUS_BRAK = "brak AED w danych"


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    k = 111_320.0
    return math.hypot((lat2 - lat1) * k, (lon2 - lon1) * k * math.cos(math.radians((lat1 + lat2) / 2)))


def build_gaps(records: list[dict], gminy: list[dict], trust: dict[str, int],
               publishers: dict[str, str], today: date | None = None) -> list[dict]:
    """trust: id źródła -> poziom zaufania; publishers: TERYT gminy -> id źródła, które ją publikuje."""
    today = today or date.today()
    fresh_from = (today - timedelta(days=365)).isoformat()
    by_gmina: dict[str, list[dict]] = defaultdict(list)
    for rec in records:
        if rec.get("kod_teryt_gminy"):
            by_gmina[rec["kod_teryt_gminy"]].append(rec)

    rows = []
    for g in gminy:
        recs = by_gmina.get(g["teryt"], [])
        # Rekord, który dysponent opublikował poza swoją gminą, to błąd danych – nie liczy się jako zweryfikowany.
        verified = [r for r in recs if trust.get(r["zrodlo"], 3) <= 2 and not _outside(r)]
        social = [r for r in recs if trust.get(r["zrodlo"], 3) >= 3]
        unmatched = [r for r in social if not _near_any(r, verified)]
        total = len(verified) + len(unmatched)
        publishes = g["teryt"] in publishers
        if publishes:
            status = STATUS_PUBLIKUJE
        elif verified:
            status = STATUS_CZESCIOWO
        elif unmatched:
            status = STATUS_TYLKO_SPOLECZNE
        else:
            status = STATUS_BRAK
        area = g.get("powierzchnia_km2") or 0
        rows.append({
            "kod_teryt_gminy": g["teryt"],
            "gmina": g["nazwa"],
            "wojewodztwo": WOJEWODZTWA.get(g["teryt"][:2], ""),
            "status": status,
            "aed_lacznie": total,
            "aed_zweryfikowane": len(verified),
            "aed_niezweryfikowane": len(unmatched),
            "osm_potwierdzone_przez_zrodlo_publiczne": len(social) - len(unmatched),
            "niezweryfikowane_z_dysponentem": sum(bool(r["dysponent_nazwa"]) for r in unmatched),
            "niezweryfikowane_sprawdzone_12_mies": sum(r["data_weryfikacji"] >= fresh_from for r in unmatched
                                                        if r["data_weryfikacji"]),
            "publicznie_24h": sum(r["dostep"] == "publiczny" and r["dostepny_24h"] == "tak"
                                  for r in verified + unmatched),
            "powierzchnia_km2": area,
            "aed_na_100_km2": round(100 * total / area, 2) if area else "",
            "zbior_na_dane_gov_pl": publishers.get(g["teryt"], ""),
        })
    rows.sort(key=lambda r: (r["wojewodztwo"], r["gmina"]))
    return rows


def summary(rows: list[dict]) -> dict:
    statuses = defaultdict(int)
    for r in rows:
        statuses[r["status"]] += 1
    woj: dict[str, dict] = defaultdict(lambda: defaultdict(int))
    for r in rows:
        w = woj[r["wojewodztwo"]]
        w["gminy"] += 1
        w["aed_zweryfikowane"] += r["aed_zweryfikowane"]
        w["aed_niezweryfikowane"] += r["aed_niezweryfikowane"]
        w["gminy_bez_aed"] += r["status"] == STATUS_BRAK
        w["gminy_publikujace"] += r["status"] == STATUS_PUBLIKUJE
    return {
        "gminy": len(rows),
        "gminy_wg_statusu": dict(statuses),
        "aed_zweryfikowane": sum(r["aed_zweryfikowane"] for r in rows),
        "aed_niezweryfikowane": sum(r["aed_niezweryfikowane"] for r in rows),
        "wojewodztwa": {k: dict(v) for k, v in sorted(woj.items())},
    }


def outside_publisher_area(records: list[dict], source_teryt: dict[str, str]) -> list[dict]:
    """Rekordy, które dysponent opublikował dla swojej gminy, a leżą poza nią."""
    return [
        r for r in records
        if r["zrodlo"] in source_teryt and r.get("kod_teryt_gminy")
        and r["kod_teryt_gminy"] != source_teryt[r["zrodlo"]]
    ]


OUTSIDE_NOTE = "AED poza obszarem dysponenta"


def _outside(rec: dict) -> bool:
    return any(note.startswith(OUTSIDE_NOTE) for note in rec.get("_uwagi", []))


def verification(records: list[dict], trust: dict[str, int]) -> list[dict]:
    """Status weryfikacji każdego rekordu według tych samych reguł co mapa luk.

    Zwraca listę (w kolejności records) słowników: poziom_zaufania, zweryfikowany,
    poza_obszarem_dysponenta, ten_sam_co (id_aed zweryfikowanego AED do 50 m – tylko dla OSM).
    """
    # Rekord bez poprawnych współrzędnych nie może potwierdzić punktu obok – i nie może wywrócić buildu.
    verified = [r for r in records
                if trust.get(r["zrodlo"], 3) <= 2 and not _outside(r) and _coords(r) is not None]
    out = []
    for rec in records:
        level = trust.get(rec["zrodlo"], 3)
        outside = _outside(rec)
        same = _nearest_within(rec, verified) if level >= 3 else None
        out.append({
            "poziom_zaufania": level,
            "zweryfikowany": level <= 2 and not outside,
            "poza_obszarem_dysponenta": outside,
            "ten_sam_co": same.get("id_aed", "") if same else "",
        })
    return out


def _coords(rec: dict) -> tuple[float, float] | None:
    try:
        return float(rec["szerokosc_geo"]), float(rec["dlugosc_geo"])
    except (KeyError, TypeError, ValueError):
        return None


def _nearest_within(rec: dict, others: list[dict], radius: float = MATCH_RADIUS_M) -> dict | None:
    """others muszą mieć poprawne współrzędne (verification() je filtruje)."""
    here = _coords(rec)
    if here is None:
        return None
    lat, lon = here
    best, best_d = None, radius
    for o in others:
        olat, olon = _coords(o)
        d = distance_m(lat, lon, olat, olon)
        if d <= best_d:
            best, best_d = o, d
    return best


def _near_any(rec: dict, others: list[dict]) -> bool:
    if not others:
        return False
    lat, lon = float(rec["szerokosc_geo"]), float(rec["dlugosc_geo"])
    return any(
        distance_m(lat, lon, float(o["szerokosc_geo"]), float(o["dlugosc_geo"])) <= MATCH_RADIUS_M
        for o in others
    )
