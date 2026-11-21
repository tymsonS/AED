"""Adapter eksportu OpenAEDMap (OpenStreetMap) dla całej Polski.

Jeden plik GeoJSON z wszystkimi AED w Polsce, poziom zaufania 3 (dane społeczne,
licencja ODbL). Służy jako narzędzie robocze – mapa luk i podpowiedź dla dostawcy,
gdzie sprawdzić AED. Do pakietu dostawcy nie trafia (portal dopuszcza tylko CC).
Tagi OSM: https://wiki.openstreetmap.org/wiki/Tag:emergency%3Ddefibrillator
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .. import normalize
from ..fields import empty_record
from .base import Adapter, http_get

# access=* (OSM) -> dostep (schemat)
ACCESS_MAP = {
    "yes": "publiczny",
    "permissive": "publiczny",
    "public": "publiczny",
    "customers": "ograniczony",
    "permit": "ograniczony",
    "delivery": "ograniczony",
    "destination": "ograniczony",
    "private": "prywatny",
    "no": "prywatny",
}
_DATE = re.compile(r"^(\d{4})-(\d{2})(?:-(\d{2}))?$")


class OpenAedMapAdapter(Adapter):
    def fetch(self) -> Path:
        body = http_get(self.source["download_url"], accept="application/geo+json, application/json")
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        path = self.raw_dir / f"resource-{self.source['country']}.geojson"
        path.write_bytes(body)
        (self.raw_dir / "meta.json").write_text(
            json.dumps(
                {
                    "download_url": self.source["download_url"],
                    "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return path

    def parse(self, path: Path) -> list[dict]:
        out = []
        for feat in json.loads(path.read_text(encoding="utf-8")).get("features", []):
            props = dict(feat.get("properties") or {})
            geom = feat.get("geometry") or {}
            if geom.get("type") == "Point":
                props["_lon"], props["_lat"] = geom["coordinates"][:2]
            out.append(props)
        return out

    def map_record(self, raw: dict) -> dict:
        rec = empty_record()
        uwagi: list[str] = []
        tag = lambda k: normalize.clean_text(str(raw.get(k, "") or ""))  # noqa: E731

        rec["id_zrodlowe"] = f"{raw.get('@osm_type', 'node')}/{raw.get('@osm_id', '')}"
        try:
            lat, lon, swapped = normalize.fix_coordinates(float(raw["_lat"]), float(raw["_lon"]))
            rec["szerokosc_geo"], rec["dlugosc_geo"] = f"{lat:.6f}", f"{lon:.6f}"
            if swapped:
                uwagi.append("współrzędne zamienione miejscami w źródle")
        except (KeyError, TypeError, ValueError):
            uwagi.append("brak lub błędne współrzędne")

        rec["nazwa_obiektu"] = tag("name") or tag("description:pl") or tag("description") or tag("operator")
        rec["opis_lokalizacji"] = tag("defibrillator:location:pl") or tag("defibrillator:location")
        rec["miejscowosc"] = tag("addr:city")
        rec["ulica"] = tag("addr:street")
        rec["numer_budynku"] = tag("addr:housenumber")
        if re.fullmatch(r"\d{2}-\d{3}", tag("addr:postcode")):
            rec["kod_pocztowy"] = tag("addr:postcode")

        level = tag("level")
        if re.fullmatch(r"-?\d+", level):
            rec["kondygnacja"] = level
        indoor = tag("indoor")
        if indoor in ("yes", "no"):
            rec["w_budynku"] = "tak" if indoor == "yes" else "nie"  # schemat: boolean, trueValues tak

        access = tag("access")
        rec["dostep"] = ACCESS_MAP.get(access, "nieznany")
        if access and access not in ACCESS_MAP:
            uwagi.append(f"nieznana wartość access={access}")

        hours = tag("opening_hours")
        rec["godziny_dostepnosci"] = hours or "nieznane"
        rec["dostepny_24h"] = "tak" if hours == "24/7" else "nie" if hours else "nieznane"

        operator = tag("operator")
        rec["dysponent_nazwa"] = operator
        # Telefon tylko instytucji (AGENTS.md): bierzemy go wyłącznie, gdy znany jest operator.
        if operator:
            rec["telefon_kontaktowy"] = normalize.normalize_phone(tag("phone").split(";")[0])

        rec["producent"] = tag("manufacturer")
        rec["model"] = tag("model")
        image = tag("image")
        rec["zdjecie_url"] = image if image.startswith("https://") else ""

        rec["data_weryfikacji"] = _osm_date(tag("check_date") or tag("survey:date"))
        rec["metoda_weryfikacji"] = "zgloszenie_spoleczne"
        rec["status"] = "nieznany"
        rec["zrodlo"] = self.id
        rec["licencja"] = self.source["licencja"]
        rec["data_aktualizacji"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        rec["id_aed"] = normalize.stable_id(self.id, rec["id_zrodlowe"])
        rec["_uwagi"] = uwagi
        return rec


def _osm_date(text: str) -> str:
    """check_date bywa „2024-05-12” albo „2024-05” – zwraca datę ISO albo pusty tekst."""
    m = _DATE.match(text)
    if not m:
        return ""
    return f"{m[1]}-{m[2]}-{m[3] or '01'}"
