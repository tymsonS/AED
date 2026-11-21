"""Bazowy adapter źródła danych."""

from __future__ import annotations

import json
import math
import re
import urllib.request
from abc import ABC, abstractmethod
from pathlib import Path

USER_AGENT = "misja-aed-ingest/0.1 (HackNation 2026)"


class Adapter(ABC):
    """Jedno źródło = jedna instancja. Kolejność: fetch() -> parse() -> map_record()."""

    def __init__(self, source: dict, raw_dir: Path):
        self.source = source
        self.id: str = source["id"]
        self.raw_dir = raw_dir / self.id

    @abstractmethod
    def fetch(self) -> Path:
        """Pobiera surowe dane do raw_dir (bez modyfikacji) i zwraca ścieżkę pliku."""

    @abstractmethod
    def parse(self, path: Path) -> list[dict]:
        """Czyta surowy plik i zwraca rekordy w układzie źródła."""

    @abstractmethod
    def map_record(self, raw: dict) -> dict:
        """Mapuje jeden rekord źródła na pola wzorcowego zakresu danych."""

    def records(self, path: Path) -> list[dict]:
        return drop_shared_photos([self.map_record(r) for r in self.parse(path)])


# Ten sam plik zdjęcia przy co najmniej tylu AED rozrzuconych dalej niż SHARED_PHOTO_SPREAD_M
# to nie zdjęcie miejsca, tylko np. ikona. AED stojące obok siebie (np. dwa wejścia) mogą mieć
# jedno prawdziwe zdjęcie miejsca, więc ich nie ruszamy.
SHARED_PHOTO_MIN = 3
SHARED_PHOTO_SPREAD_M = 500


def photo_key(url: str) -> str:
    """Adres pliku bez opisowej końcówki CMS: „…/download/156869/<nazwa>” -> „…/download/156869”.

    Końcówkę obcinamy tylko, gdy jest opisem (nie samą liczbą) bez rozszerzenia po segmencie
    z numerem – plik „…/uploads/2026/03/zdjecie.jpg” i „…/galeria/2024/5678” zostają bez zmian. Parametry zapytania zostają (edupage,
    Facebook trzymają w nich numer zdjęcia). W zbiorze Przemyśla 21 AED ma adresy różniące się
    tylko końcówką, a serwer zwraca ten sam plik (znak „AED”) – sprawdzone 21.11.2026 (MD5).
    """
    base, sep, query = url.partition("?")
    base = base.rstrip("/")
    head, _, last = base.rpartition("/")
    # Sama liczba na końcu (…/galeria/2024/5678) to numer zdjęcia, nie opisowa końcówka (review #49).
    if "." not in last and not last.isdigit() and re.search(r"/\d+$", head):
        base = head
    return base + sep + query


def _spread_m(records: list[dict]) -> float:
    coords = []
    for r in records:
        try:
            coords.append((float(r["szerokosc_geo"]), float(r["dlugosc_geo"])))
        except (KeyError, ValueError):
            continue
    if len(coords) < 2:
        return 0.0
    lats, lons = [c[0] for c in coords], [c[1] for c in coords]
    mid = math.radians(sum(lats) / len(lats))
    return math.hypot((max(lats) - min(lats)) * 111_320, (max(lons) - min(lons)) * 111_320 * math.cos(mid))


def drop_shared_photos(records: list[dict]) -> list[dict]:
    """Czyści zdjecie_url, gdy ten sam plik powtarza się przy co najmniej SHARED_PHOTO_MIN AED
    rozrzuconych na więcej niż SHARED_PHOTO_SPREAD_M (jedno zdjęcie nie pokazuje wielu miejsc)."""
    groups: dict[str, list[dict]] = {}
    for rec in records:
        if rec.get("zdjecie_url"):
            groups.setdefault(photo_key(rec["zdjecie_url"]), []).append(rec)
    for recs in groups.values():
        if len(recs) < SHARED_PHOTO_MIN or _spread_m(recs) <= SHARED_PHOTO_SPREAD_M:
            continue
        for rec in recs:
            rec["zdjecie_url"] = ""
            rec.setdefault("_uwagi", []).append(
                f"zdjecie_url pominięte – ten sam plik przy {len(recs)} AED w różnych miejscach "
                "(np. ikona, nie zdjęcie miejsca)")
    return records


def http_get(url: str, accept: str = "*/*", timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def http_get_json(url: str) -> dict:
    return json.loads(http_get(url, accept="application/json"))
