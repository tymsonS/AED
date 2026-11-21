"""Pakiet dla dystrybutora: lista AED do potwierdzenia na jego obszarze.

Dystrybutor (np. Centrum Ratownictwa) zna urządzenia i ich właścicieli, więc potwierdza,
że AED jest w danym miejscu (ustalenia z mentorem, docs/plan-techniczny.md pkt 4–6).
Za stan techniczny odpowiada właściciel. Pakiet to lista robocza, nie publikacja:
zawiera też punkty z OpenStreetMap (ODbL) jako podpowiedź, gdzie sprawdzić AED.
Do publikacji na dane.gov.pl służy pakiet dostawcy (package.py).
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import export
from .gminy import WOJEWODZTWA


class DistributorError(ValueError):
    pass


# Priorytet sprawdzenia: im niższy, tym pilniej.
PRIORYTETY = {
    1: "niezweryfikowany, bez dysponenta, punkt instytucji poza jej gminą albo zgłoszony brak urządzenia",
    2: "niezweryfikowany, nigdy niesprawdzony albo sprawdzony ponad 12 mies. temu",
    3: "niezweryfikowany, sprawdzony w ostatnich 12 mies.",
    4: "zweryfikowany (dane instytucji albo potwierdzony przez dystrybutora) – przy okazji",
}

# Kolumny, które wypełnia dystrybutor. Wartości do wyboru są w CZYTAJ-MNIE.txt.
KOLUMNY_DYSTRYBUTORA = (
    "wynik_sprawdzenia",                  # potwierdzam / inne_miejsce / brak_urzadzenia / nie_sprawdzono
    "data_sprawdzenia",                   # RRRR-MM-DD
    "lokalizacje_potwierdzil",            # nazwa instytucji dystrybutora
    "odpowiedzialny_za_stan_techniczny",  # właściciel albo firma serwisowa (instytucja)
    "dysponent_poprawiony",               # gdy dysponent_nazwa jest pusty lub błędny
    "nazwa_obiektu_poprawiona",           # własnymi słowami – nazw z OSM nie publikujemy (ODbL)
    "poinformowano_dysponenta",           # RRRR-MM-DD: przy brak_urzadzenia – kiedy dysponent dostał informację
    "uwagi_dystrybutora",
)
WYNIKI = ("potwierdzam", "inne_miejsce", "brak_urzadzenia", "nie_sprawdzono")

KOLUMNY = (
    "lp", "priorytet", "powod", "status_weryfikacji", "id_aed", "zrodlo", "id_zrodlowe",
    "wojewodztwo", "gmina", "kod_teryt_gminy", "miejscowosc", "ulica", "numer_budynku",
    "nazwa_obiektu", "opis_lokalizacji", "szerokosc_geo", "dlugosc_geo", "mapa_url",
    "dysponent_nazwa", "dostep", "godziny_dostepnosci", "data_weryfikacji", "licencja",
) + KOLUMNY_DYSTRYBUTORA


@dataclass
class DistributorMeta:
    obszar: list[str]       # kody TERYT: 2 (województwo), 4 (powiat) albo 7 cyfr (gmina)
    dystrybutor: str        # instytucja, która potwierdza lokalizacje
    nazwa_obszaru: str = ""

    def check(self) -> None:
        if not self.obszar:
            raise DistributorError("Podaj co najmniej jeden kod TERYT obszaru")
        for kod in self.obszar:
            if not re.fullmatch(r"\d{2}|\d{4}|\d{7}", kod):
                raise DistributorError(f"TERYT {kod!r}: musi mieć 2, 4 albo 7 cyfr")
            if kod[:2] not in WOJEWODZTWA:
                raise DistributorError(f"TERYT {kod!r}: nieznany kod województwa {kod[:2]}")
        if not self.dystrybutor.strip():
            raise DistributorError("Podaj nazwę dystrybutora")
        if not self.nazwa_obszaru:
            self.nazwa_obszaru = ", ".join(_area_label(k) for k in self.obszar)

    @property
    def ident(self) -> str:
        codes = "-".join(self.obszar)
        if len(codes) > 60:
            # Długie zestawy o tym samym początku nie mogą trafić do jednego katalogu.
            codes = codes[:50] + "-" + hashlib.sha1(codes.encode()).hexdigest()[:8]
        return "dystrybutor-" + codes


def slug(text: str, limit: int = 40) -> str:
    """„Centrum Ratownictwa Łódź” -> „centrum-ratownictwa-lodz” (do nazw plików)."""
    import unicodedata

    ascii_text = unicodedata.normalize("NFKD", text.replace("ł", "l").replace("Ł", "L"))
    ascii_text = ascii_text.encode("ascii", "ignore").decode().lower()
    return "-".join(re.findall(r"[a-z0-9]+", ascii_text))[:limit].strip("-") or "dystrybutor"


def in_area(rec: dict, obszar: list[str]) -> bool:
    teryt = rec.get("kod_teryt_gminy", "")
    return bool(teryt) and any(teryt.startswith(kod) for kod in obszar)


def build_worklist(records: list[dict], statuses: list[dict], meta: DistributorMeta,
                   today: date | None = None) -> tuple[list[dict], dict]:
    """Lista AED do potwierdzenia i podsumowanie.

    statuses: wynik gaps.verification() dla records (ta sama kolejność).
    Punkt OSM, który jest tym samym AED co zweryfikowany (ten_sam_co), nie trafia na listę
    drugi raz – dystrybutor sprawdza urządzenie, a nie wpis.
    """
    meta.check()
    today = today or date.today()
    fresh_from = (today - timedelta(days=365)).isoformat()
    rows, pominiete_duplikaty = [], 0
    for rec, st in zip(records, statuses, strict=True):
        if not in_area(rec, meta.obszar):
            continue
        if st["ten_sam_co"]:
            pominiete_duplikaty += 1
            continue
        prio = _priority(rec, st, fresh_from, today.isoformat())
        row = {k: rec.get(k, "") for k in KOLUMNY if k in rec}
        row.update(
            priorytet=prio,
            powod=_reason(rec, st, prio),
            status_weryfikacji="zweryfikowany" if st["zweryfikowany"] else "niezweryfikowany",
            mapa_url=_map_url(rec),
            **{k: "" for k in KOLUMNY_DYSTRYBUTORA},
        )
        rows.append(row)
    rows.sort(key=lambda r: (r["gmina"], r["miejscowosc"], r["priorytet"], r["ulica"], r["numer_budynku"]))
    for i, row in enumerate(rows, 1):
        row["lp"] = i
    return rows, _summary(rows, meta, pominiete_duplikaty)


def write_distributor_package(records: list[dict], statuses: list[dict], meta: DistributorMeta,
                              out_dir: Path, today: date | None = None) -> dict[str, Path]:
    rows, summ = build_worklist(records, statuses, meta, today)
    if not rows:
        raise DistributorError(f"Brak AED w danych na obszarze {meta.nazwa_obszaru} – sprawdź kody TERYT")
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "csv": out_dir / "do-potwierdzenia.csv",
        "geojson": out_dir / "do-potwierdzenia.geojson",
        "podsumowanie": out_dir / "podsumowanie.json",
        "instrukcja": out_dir / "CZYTAJ-MNIE.txt",
    }
    # UTF-8 z BOM: Excel otwiera wtedy polskie znaki poprawnie – to plik do pracy, nie do portalu.
    with paths["csv"].open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=KOLUMNY, lineterminator="\n")
        writer.writeheader()
        writer.writerows({k: excel_safe(v) for k, v in r.items()} for r in rows)
    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [float(r["dlugosc_geo"]), float(r["szerokosc_geo"])]},
            "properties": {k: r[k] for k in KOLUMNY if k not in ("szerokosc_geo", "dlugosc_geo")},
        }
        for r in rows
    ]
    paths["geojson"].write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False,
                   separators=(",", ":")),
        encoding="utf-8",
    )
    export.write_json(summ, paths["podsumowanie"])
    paths["instrukcja"].write_text(_instructions(meta, summ), encoding="utf-8")
    return paths


# Excel wykonuje komórkę zaczynającą się od tych znaków jako formułę (CSV injection).
_FORMULA_START = ("=", "+", "-", "@", "\t", "\r")


def excel_safe(value):
    """Tekst z OSM może edytować każdy – apostrof na początku wyłącza formułę w Excelu."""
    if isinstance(value, str) and value.startswith(_FORMULA_START):
        return "'" + value
    return value


def _priority(rec: dict, st: dict, fresh_from: str, today: str) -> int:
    if st["zweryfikowany"]:
        return 4
    # Punkt instytucji poza jej gminą albo zgłoszony brak urządzenia – do wyjaśnienia najpierw.
    if st["poza_obszarem_dysponenta"] or st.get("zgloszony_brak") or not rec.get("dysponent_nazwa"):
        return 1
    checked = rec.get("data_weryfikacji", "")
    # Data z przyszłości to literówka w źródle, a nie świeże sprawdzenie.
    return 3 if checked and fresh_from <= checked <= today else 2


def _reason(rec: dict, st: dict, prio: int) -> str:
    if st.get("zgloszony_brak"):
        return f"zgłoszony brak urządzenia ({rec.get('_zgloszony_brak', '')}) – wyjaśnij z dysponentem"
    if st["poza_obszarem_dysponenta"]:
        return "instytucja opublikowała punkt poza swoją gminą – sprawdź, czy to właściwe miejsce"
    if prio == 4 and rec.get("lokalizacje_potwierdzil"):
        return f"lokalizację potwierdził {rec['lokalizacje_potwierdzil']} ({rec.get('data_weryfikacji') or 'brak daty'})"
    if prio == 4:
        return f"dane instytucji ({rec.get('dysponent_nazwa') or rec.get('zrodlo')})"
    parts = ["dane społeczne (OpenStreetMap)" if st["poziom_zaufania"] >= 3 else "dane instytucji, niezweryfikowane"]
    if not rec.get("dysponent_nazwa"):
        parts.append("brak dysponenta")
    if not rec.get("data_weryfikacji"):
        parts.append("nigdy niesprawdzony")
    elif prio == 2:
        parts.append(f"ostatnio sprawdzony {rec['data_weryfikacji']}")
    return ", ".join(parts)


def _map_url(rec: dict) -> str:
    if rec.get("zrodlo", "").startswith("osm") and "/" in rec.get("id_zrodlowe", ""):
        return f"https://www.openstreetmap.org/{rec['id_zrodlowe']}"
    lat, lon = rec.get("szerokosc_geo", ""), rec.get("dlugosc_geo", "")
    return f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=19/{lat}/{lon}"


def _summary(rows: list[dict], meta: DistributorMeta, duplikaty: int) -> dict:
    by_gmina: dict[tuple[str, str], Counter] = defaultdict(Counter)
    for r in rows:
        c = by_gmina[(r["kod_teryt_gminy"], r["gmina"])]
        c["aed"] += 1
        c[f"priorytet_{r['priorytet']}"] += 1
    return {
        "dystrybutor": meta.dystrybutor,
        "obszar": meta.obszar,
        "nazwa_obszaru": meta.nazwa_obszaru,
        "wygenerowano": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "aed_do_sprawdzenia": len(rows),
        "zweryfikowane": sum(r["status_weryfikacji"] == "zweryfikowany" for r in rows),
        "niezweryfikowane": sum(r["status_weryfikacji"] == "niezweryfikowany" for r in rows),
        "pominiete_duplikaty_osm": duplikaty,
        "wg_priorytetu": {f"{p} – {opis}": sum(r["priorytet"] == p for r in rows) for p, opis in PRIORYTETY.items()},
        "gminy": [
            {"kod_teryt_gminy": teryt, "gmina": nazwa, "aed": c["aed"],
             **{f"priorytet_{p}": c[f"priorytet_{p}"] for p in PRIORYTETY}}
            for (teryt, nazwa), c in sorted(by_gmina.items(), key=lambda kv: (-kv[1]["priorytet_1"], kv[0][1]))
        ],
    }


def _area_label(kod: str) -> str:
    woj = WOJEWODZTWA.get(kod[:2], "?")
    if len(kod) == 2:
        return f"województwo {woj}"
    return f"{'powiat' if len(kod) == 4 else 'gmina'} {kod} ({woj})"


def _instructions(meta: DistributorMeta, summ: dict) -> str:
    prio = "\n".join(f"  {k}: {v}" for k, v in summ["wg_priorytetu"].items())
    return f"""Lista AED do potwierdzenia – {meta.nazwa_obszaru}
Dystrybutor: {meta.dystrybutor}
Wygenerowano: {summ['wygenerowano']}

AED do sprawdzenia: {summ['aed_do_sprawdzenia']} (zweryfikowane przez instytucje: {summ['zweryfikowane']},
niezweryfikowane: {summ['niezweryfikowane']}). Punkty z OpenStreetMap, które są tym samym AED
co zweryfikowany, pominięto: {summ['pominiete_duplikaty_osm']}.

Według priorytetu (1 = najpilniej):
{prio}

Pliki:
  do-potwierdzenia.csv      – lista robocza, otwiera się w Excelu (UTF-8 z BOM)
  do-potwierdzenia.geojson  – te same punkty do wczytania na mapę (np. QGIS, geojson.io)
  podsumowanie.json         – liczby dla całego obszaru i dla każdej gminy

Po co ta lista
  Dystrybutor potwierdza, że AED jest w danym miejscu. Za stan techniczny (bateria, elektrody,
  przeglądy) odpowiada właściciel urządzenia. Potwierdzone dane gmina lub właściciel publikuje
  na dane.gov.pl we wzorcowym zakresie danych (pakiet dostawcy).

Co wypełnić (ostatnie kolumny arkusza)
  wynik_sprawdzenia                  {' / '.join(WYNIKI)}
  data_sprawdzenia                   RRRR-MM-DD
  lokalizacje_potwierdzil            nazwa Twojej instytucji – tylko gdy potwierdzasz lokalizację
  odpowiedzialny_za_stan_techniczny  właściciel albo firma serwisowa (nazwa instytucji)
  dysponent_poprawiony               gdy kolumna dysponent_nazwa jest pusta lub błędna
  nazwa_obiektu_poprawiona           nazwa miejsca własnymi słowami, np. „Szkoła Podstawowa nr 3”;
                                     w wierszach z OpenStreetMap wymagana, bo nazwy z OSM nie publikujemy
  poinformowano_dysponenta           przy brak_urzadzenia: data (RRRR-MM-DD), kiedy poinformowałeś
                                     dysponenta (np. gminę) o braku urządzenia
  uwagi_dystrybutora                 np. „AED przeniesiony na II piętro”
  Przy wyniku inne_miejsce wpisz nowe współrzędne w kolumnach szerokosc_geo i dlugosc_geo.

Brak urządzenia
  Za poinformowanie instytucji o błędzie odpowiada dystrybutor. AED z OpenStreetMap usuwamy
  z naszych wyników od razu. AED z danych instytucji (np. gminy) usuwamy z naszych wyników
  dopiero, gdy w poinformowano_dysponenta jest data – do tego czasu jest oznaczony „do wyjaśnienia
  z dysponentem”. Zbiór instytucji na dane.gov.pl poprawia jego właściciel.
  Nie wpisuj danych osób prywatnych (imion, prywatnych telefonów ani e-maili).
  Nie zmieniaj kolumn id_aed i zrodlo – po nich dane wracają do zbioru.

Co wraca do zbioru po sprawdzeniu
  data_sprawdzenia zastąpi data_weryfikacji, a metoda_weryfikacji będzie „dystrybutor”.
  Do zbioru publikowanego na licencji Creative Commons trafi tylko to, co potwierdziłeś
  lub wpisałeś sam: lokalizacja, lokalizacje_potwierdzil, data_sprawdzenia,
  odpowiedzialny_za_stan_techniczny, dysponent_poprawiony i nazwa_obiektu_poprawiona.
  Nazwy, opisy, adresy, godziny i rodzaj dostępu skopiowane z OpenStreetMap (ODbL)
  nie przechodzą do publikacji – uzupełni je właściciel urządzenia.
  Plik możesz zapisać w Excelu jako CSV (przecinek albo średnik, UTF-8 albo Windows-1250).
  Wczytanie: python -m ingest wczytaj-dystrybutora do-potwierdzenia.csv --dystrybutor "…"

Licencja
  Wiersze ze źródłem osm-openaedmap pochodzą z OpenStreetMap: © współtwórcy OpenStreetMap,
  licencja ODbL (https://www.openstreetmap.org/copyright). To podpowiedź, gdzie sprawdzić AED,
  a nie dane do publikacji. Pozostałe wiersze mają licencję z kolumny licencja.
"""
