"""Granice gmin z Państwowego Rejestru Granic (GUGiK) i przypisanie punktów do gmin.

Źródło: usługa WFS PRG, warstwa A03_Granice_gmin (kod TERYT w JPT_KOD_JE).
Granice upraszczamy (Douglas-Peucker, ok. 20 m) i zapisujemy w ingest/data/prg/
jako lekki JSON – poza gitem. Przypisanie punktu: indeks siatki + ray casting,
bez zewnętrznych bibliotek.
"""

from __future__ import annotations

import json
import math
import urllib.parse
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

from .adapters.base import http_get

WFS_URL = "https://mapy.geoportal.gov.pl/wss/service/PZGIK/PRG/WFS/AdministrativeBoundaries"
LAYER = "ms:A03_Granice_gmin"
PAGE = 200
TOLERANCE_DEG = 0.0002  # ok. 20 m – wystarcza do przypisania AED do gminy
CELL_DEG = 0.1

GML = "{http://www.opengis.net/gml/3.2}"
MS = "{http://mapserver.gis.umn.edu/mapserver}"

# Pierwsze dwie cyfry TERYT -> województwo
WOJEWODZTWA = {
    "02": "dolnośląskie", "04": "kujawsko-pomorskie", "06": "lubelskie", "08": "lubuskie",
    "10": "łódzkie", "12": "małopolskie", "14": "mazowieckie", "16": "opolskie",
    "18": "podkarpackie", "20": "podlaskie", "22": "pomorskie", "24": "śląskie",
    "26": "świętokrzyskie", "28": "warmińsko-mazurskie", "30": "wielkopolskie", "32": "zachodniopomorskie",
}


# --- pobieranie ---------------------------------------------------------------

def fetch_gminy(dest: Path, page: int = PAGE) -> Path:
    """Pobiera wszystkie gminy z WFS PRG stronami i zapisuje uproszczone granice."""
    gminy: list[dict] = []
    start = 0
    while True:
        params = {
            "SERVICE": "WFS", "VERSION": "2.0.0", "REQUEST": "GetFeature",
            "TYPENAMES": LAYER, "COUNT": str(page), "STARTINDEX": str(start),
            "SRSNAME": "urn:ogc:def:crs:EPSG::4326",
        }
        batch = parse_gml(http_get(f"{WFS_URL}?{urllib.parse.urlencode(params)}", timeout=300))
        gminy.extend(batch)
        print(f"  gminy: {len(gminy)}")
        if len(batch) < page:
            break
        start += page
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(gminy, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return dest


def parse_gml(body: bytes) -> list[dict]:
    out = []
    root = ET.fromstring(body)
    for feat in root.iter(f"{MS}A03_Granice_gmin"):
        teryt = (feat.findtext(f"{MS}JPT_KOD_JE") or "").strip()
        if not teryt:
            continue
        polygons = []
        for poly in feat.iter(f"{GML}Polygon"):
            rings = []
            for tag in ("exterior", "interior"):
                for ring in poly.findall(f"{GML}{tag}"):
                    pos = ring.find(f".//{GML}posList")
                    if pos is not None and pos.text:
                        rings.append(simplify(_poslist_lonlat(pos.text), TOLERANCE_DEG))
            if rings:
                polygons.append(rings)
        area = feat.findtext(f"{MS}JPT_POWIER") or "0"
        out.append({
            "teryt": teryt,
            "nazwa": (feat.findtext(f"{MS}JPT_NAZWA_") or "").strip(),
            "powierzchnia_km2": round(float(area) / 100, 2),  # JPT_POWIER w hektarach
            "polygons": polygons,
        })
    return out


def _poslist_lonlat(text: str) -> list[list[float]]:
    """posList w EPSG:4326 ma kolejność szerokość, długość – zamieniamy na [lon, lat]."""
    nums = [float(x) for x in text.split()]
    return [[round(nums[i + 1], 6), round(nums[i], 6)] for i in range(0, len(nums) - 1, 2)]


def simplify(points: list[list[float]], tol: float) -> list[list[float]]:
    """Douglas-Peucker (iteracyjnie), zachowuje pierwszy i ostatni punkt pierścienia."""
    if len(points) < 5:
        return points
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        a, b = stack.pop()
        ax, ay = points[a]
        bx, by = points[b]
        dx, dy = bx - ax, by - ay
        norm = math.hypot(dx, dy)
        best, idx = 0.0, -1
        for i in range(a + 1, b):
            px, py = points[i]
            if norm < 1e-12:  # zamknięty pierścień: końce w tym samym punkcie
                d = math.hypot(px - ax, py - ay)
            else:
                d = abs(dy * px - dx * py + bx * ay - by * ax) / norm
            if d > best:
                best, idx = d, i
        if best > tol and idx > 0:
            keep[idx] = True
            stack.extend(((a, idx), (idx, b)))
    return [p for p, k in zip(points, keep) if k]


# --- przypisanie punktów ------------------------------------------------------

class GminaIndex:
    def __init__(self, gminy: list[dict]):
        self.gminy = gminy
        self.grid: dict[tuple[int, int], list[int]] = defaultdict(list)
        self.bbox = []
        for i, g in enumerate(gminy):
            xs = [p[0] for poly in g["polygons"] for p in poly[0]]
            ys = [p[1] for poly in g["polygons"] for p in poly[0]]
            box = (min(xs), min(ys), max(xs), max(ys)) if xs else (0, 0, 0, 0)
            self.bbox.append(box)
            for cx in range(_cell(box[0]), _cell(box[2]) + 1):
                for cy in range(_cell(box[1]), _cell(box[3]) + 1):
                    self.grid[(cx, cy)].append(i)

    @classmethod
    def load(cls, path: Path) -> "GminaIndex":
        return cls(json.loads(path.read_text(encoding="utf-8")))

    def find(self, lon: float, lat: float) -> dict | None:
        # Uproszczone granice sąsiednich gmin mogą zostawić wąskie szczeliny (do ok. 20 m),
        # więc gdy punkt nie trafi w żadną gminę, sprawdzamy punkty przesunięte o ok. 30 m.
        for dx, dy in _PROBES:
            x, y = lon + dx, lat + dy
            for i in self.grid.get((_cell(x), _cell(y)), ()):
                x0, y0, x1, y1 = self.bbox[i]
                if x0 <= x <= x1 and y0 <= y <= y1 and _in_gmina(x, y, self.gminy[i]["polygons"]):
                    return self.gminy[i]
        return None


_D = 0.0004
_PROBES = [(0.0, 0.0)] + [(dx * _D, dy * _D) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy]


def _cell(v: float) -> int:
    return math.floor(v / CELL_DEG)


def _in_gmina(x: float, y: float, polygons: list) -> bool:
    for rings in polygons:
        if _in_ring(x, y, rings[0]) and not any(_in_ring(x, y, hole) for hole in rings[1:]):
            return True
    return False


def _in_ring(x: float, y: float, ring: list) -> bool:
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def enrich(records: list[dict], index: GminaIndex) -> int:
    """Uzupełnia kod_teryt_gminy, gmina i wojewodztwo. Zwraca liczbę przypisanych rekordów."""
    hit = 0
    for rec in records:
        try:
            lon, lat = float(rec["dlugosc_geo"]), float(rec["szerokosc_geo"])
        except (KeyError, ValueError):
            continue
        g = index.find(lon, lat)
        if g is None:
            continue
        hit += 1
        rec["kod_teryt_gminy"] = g["teryt"]
        rec["gmina"] = g["nazwa"]
        rec["wojewodztwo"] = WOJEWODZTWA.get(g["teryt"][:2], "")
    return hit
