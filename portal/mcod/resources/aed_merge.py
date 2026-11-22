"""Scalanie zasobów AED wielu instytucji w jeden wykaz zbiorczy (AEDane, HackNation 2026).

Moduł bez zależności od Django i pandas – logikę da się testować bez działającego portalu.
Część zależną od modeli (wybór zasobów, publikacja wyniku) zawiera aed_utils.py, a zadanie
Celery tasks/aed.py – oba na wzór Wykazu Głównego DGA (dga_utils.py, tasks/dga.py).

Różnice względem DGA:
- DGA tylko skleja wiersze; ten sam AED może być w zasobie gminy i w zasobie szpitala, więc
  wiersze z tym samym id_aed scalamy (zostaje nowsza data_weryfikacji, a przy remisie wiersz
  z potwierdzoną lokalizacją), a AED innych instytucji w promieniu 50 m oznaczamy jako
  możliwy duplikat zamiast go usuwać,
- błędny wiersz pomijamy pojedynczo (z powodem w raporcie), a nie cały zasób.

id_aed (gdy zasób go nie podaje) liczymy z identyfikatora instytucji, a nie z numeru zasobu –
ponowne wgranie pliku przez gminę (nowy zasób) nie zmienia identyfikatorów AED (review #58).
"""

import math
import re
import uuid
from typing import Dict, Iterable, List, Optional, Tuple

# Wzorcowy zakres danych AED v0.2 (schema/aed.schema.json w repozytorium AEDane), w kolejności schematu.
AED_COLUMNS: List[str] = [
    "id_aed", "id_zrodlowe", "numer_seryjny", "szerokosc_geo", "dlugosc_geo", "wojewodztwo", "powiat",
    "gmina", "kod_teryt_gminy", "miejscowosc", "ulica", "numer_budynku", "kod_pocztowy", "nazwa_obiektu",
    "opis_lokalizacji", "kondygnacja", "w_budynku", "dostep", "godziny_dostepnosci", "dostepny_24h",
    "szafka_zamykana", "kod_do_szafki_u_dyspozytora", "producent", "model", "tryb_pediatryczny", "status",
    "data_przegladu", "data_waznosci_elektrod", "data_waznosci_baterii", "odpowiedzialny_za_stan_techniczny",
    "dysponent_nazwa", "dysponent_regon", "dysponent_nip", "telefon_kontaktowy", "data_weryfikacji",
    "metoda_weryfikacji", "lokalizacje_potwierdzil", "zdjecie_url", "zrodlo", "licencja", "data_aktualizacji",
]

# Bez tych kolumn zasób nie może wejść do wykazu (jak MAIN_DGA_REQUIRED_SOURCE_COLUMNS).
AED_REQUIRED_SOURCE_COLUMNS: List[str] = ["szerokosc_geo", "dlugosc_geo", "nazwa_obiektu"]

# Kolumny dodawane przez portal przy scalaniu (odpowiednik „Nazwa dysponenta zasobu” w DGA).
MAIN_AED_EXTRA_COLUMNS: List[str] = ["instytucja_publikujaca", "id_zasobu_zrodlowego", "mozliwy_duplikat"]
MAIN_AED_COLUMNS: List[str] = AED_COLUMNS + MAIN_AED_EXTRA_COLUMNS

# Granice Polski jak w schemacie (constraints minimum/maximum dla współrzędnych).
LAT_MIN, LAT_MAX, LON_MIN, LON_MAX = 49.0, 54.9, 14.1, 24.2
DUPLICATE_RADIUS_M = 50
AED_NAMESPACE = uuid.UUID("6f1c2a52-8d8b-4c39-9f1e-0d6a2b7c4e11")


class EmptyAEDListError(Exception):
    """Wynik scalania jest pusty – nie publikujemy go w miejsce poprzedniego wykazu."""


class MissingRequiredColumnsError(Exception):
    def __init__(self, column_names: List[str]):
        self.column_names = column_names
        super().__init__(f"Brak wymaganych kolumn: {', '.join(column_names)}")


def missing_required_columns(columns: Iterable[str]) -> List[str]:
    present = set(columns)
    return [c for c in AED_REQUIRED_SOURCE_COLUMNS if c not in present]


def parse_coordinate(value) -> Optional[float]:
    """Liczba z kropką albo przecinkiem dziesiętnym (pliki z Excela); None, gdy to nie liczba skończona."""
    if value is None:
        return None
    text = str(value).strip().replace(",", ".")
    try:
        number = float(text)
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    k = 111_320.0
    return math.hypot((lat2 - lat1) * k, (lon2 - lon1) * k * math.cos(math.radians((lat1 + lat2) / 2)))


def stable_aed_id(institution_key: str, source_id: str) -> str:
    """id_aed nadawane przez system (schemat: x-nadaje-system), stałe dla tej samej pary."""
    return str(uuid.uuid5(AED_NAMESPACE, f"{institution_key}:{source_id}"))


def normalize_row(row: Dict, institution: str, institution_key, resource_id,
                  used_keys: Optional[set] = None) -> Tuple[Optional[Dict], Optional[str]]:
    """Wiersz zasobu -> wiersz wykazu albo (None, powód pominięcia).

    used_keys – klucze już nadane w tym zasobie: dwa AED w tym samym miejscu bez id_zrodlowe
    (np. dwa wejścia budynku) dostają klucz z dopiskiem -2, -3… – ta sama reguła co w ingest/package.py.
    """
    out = {c: "" if row.get(c) is None else str(row.get(c)).strip() for c in AED_COLUMNS}
    lat, lon = parse_coordinate(out["szerokosc_geo"]), parse_coordinate(out["dlugosc_geo"])
    if lat is None or lon is None:
        return None, "brak poprawnych współrzędnych"
    if not (LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX):
        return None, "współrzędne poza Polską"
    if not out["nazwa_obiektu"]:
        return None, "brak nazwy obiektu"
    out["szerokosc_geo"], out["dlugosc_geo"] = f"{lat:.6f}", f"{lon:.6f}"
    if not out["id_aed"]:
        key = out["id_zrodlowe"]
        if not key:
            base = f"wsp-{lat:.6f}-{lon:.6f}"
            n, key = 1, base
            while used_keys is not None and key in used_keys:
                n += 1
                key = f"{base}-{n}"
        if used_keys is not None:
            used_keys.add(key)
        out["id_aed"] = stable_aed_id(str(institution_key), key)
    out["instytucja_publikujaca"] = institution
    out["id_zasobu_zrodlowego"] = str(resource_id)
    out["mozliwy_duplikat"] = ""
    return out, None


def _rank(row: Dict) -> Tuple[str, int]:
    # Nowsza data weryfikacji wygrywa, przy remisie wiersz z potwierdzoną lokalizacją.
    return row.get("data_weryfikacji", ""), 1 if row.get("lokalizacje_potwierdzil") else 0


def merge_sources(sources: Iterable[Tuple[str, object, object, List[Dict]]]) -> Tuple[List[Dict], List[Dict]]:
    """Scala zasoby: [(nazwa instytucji, id instytucji, id zasobu, wiersze), ...] -> (wiersze wykazu, raport pominięć).

    Wiersze z tym samym id_aed scalamy w jeden; AED różnych instytucji bliżej niż 50 m oznaczamy
    w kolumnie mozliwy_duplikat (id_aed drugiego), bez usuwania – rozstrzyga dysponent.
    """
    by_id: Dict[str, Dict] = {}
    skipped: List[Dict] = []
    for institution, institution_key, resource_id, rows in sources:
        # Dopiski -2, -3 tylko w obrębie zasobu: ten sam AED w dwóch zasobach instytucji ma to samo id.
        used_keys: set = set()
        for number, row in enumerate(rows, start=1):
            rec, reason = normalize_row(row, institution, institution_key, resource_id, used_keys)
            if rec is None:
                skipped.append({"id_zasobu_zrodlowego": str(resource_id), "instytucja": institution,
                                "wiersz": number, "powod": reason})
                continue
            current = by_id.get(rec["id_aed"])
            if current is None or _rank(rec) > _rank(current):
                by_id[rec["id_aed"]] = rec
    merged = sorted(by_id.values(), key=lambda r: (r["instytucja_publikujaca"], r["miejscowosc"], r["nazwa_obiektu"]))
    _flag_possible_duplicates(merged)
    return merged, skipped


def _flag_possible_duplicates(rows: List[Dict]) -> None:
    # Siatka ok. 0,001° (ok. 100 m), żeby nie porównywać każdego z każdym przy tysiącach AED.
    cells: Dict[Tuple[int, int], List[Dict]] = {}
    for row in rows:
        lat, lon = float(row["szerokosc_geo"]), float(row["dlugosc_geo"])
        cells.setdefault((int(lat * 1000), int(lon * 1000)), []).append(row)
    for row in rows:
        lat, lon = float(row["szerokosc_geo"]), float(row["dlugosc_geo"])
        cy, cx = int(lat * 1000), int(lon * 1000)
        near = []
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                for other in cells.get((cy + dy, cx + dx), []):
                    if (other is not row and other["instytucja_publikujaca"] != row["instytucja_publikujaca"]
                            and distance_m(lat, lon, float(other["szerokosc_geo"]),
                                           float(other["dlugosc_geo"])) <= DUPLICATE_RADIUS_M):
                        near.append(other["id_aed"])
        row["mozliwy_duplikat"] = ";".join(sorted(near))


_SAFE_FILE_CHARS = re.compile(r"[^\w\- .]+", re.UNICODE)


def safe_file_name(text: str) -> str:
    return _SAFE_FILE_CHARS.sub("", text).strip()
