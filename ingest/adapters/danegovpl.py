"""Adapter zbiorów AED opublikowanych na dane.gov.pl.

Jeden adapter obsługuje wiele zbiorów: różnice między nimi (format, nazwy kolumn)
opisuje wpis źródła w ingest/sources.toml.
"""

from __future__ import annotations

import csv
import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .. import csvio, normalize
from ..fields import empty_record
from .base import Adapter, http_get, http_get_json

API = "https://api.dane.gov.pl/1.4"

# Przemyśl: „Defibrylator (AED 9485) w ADM Centrum” -> „ADM Centrum”
# „Defibrylator (AED 9485) w ADM Centrum”, „Defibrylator (AED7646) - Rynek 1” -> nazwa obiektu
_NAME_PREFIX = re.compile(r"^defibrylator\s*(\([^)]*\))?\s*(we\s+|w\s+|[-–:]\s*)?", re.IGNORECASE)


class DaneGovPlAdapter(Adapter):
    def fetch(self) -> Path:
        rid = self.source["resource_id"]
        meta = http_get_json(f"{API}/resources/{rid}")["data"]["attributes"]
        body = http_get(meta["download_url"])
        if body.lstrip()[:15].lower().startswith((b"<!doctype html", b"<html")):
            raise RuntimeError(
                f"{self.id}: zasób {rid} zwraca stronę WWW zamiast danych ({meta['download_url']})"
            )
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        path = self.raw_dir / f"resource-{rid}.{self.source['format']}"
        path.write_bytes(body)
        (self.raw_dir / "meta.json").write_text(
            json.dumps(
                {
                    "download_url": meta["download_url"],
                    "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "modified": meta.get("modified"),
                    "data_date": meta.get("data_date"),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return path

    # --- parsowanie ---------------------------------------------------------

    def parse(self, path: Path) -> list[dict]:
        text = path.read_text(encoding="utf-8-sig")
        fmt = self.source["format"]
        if fmt == "csv":
            return parse_csv(text)
        if fmt == "geojson":
            return parse_geojson(text)
        raise ValueError(f"{self.id}: nieobsługiwany format {fmt}")

    # --- mapowanie ----------------------------------------------------------

    def map_record(self, raw: dict) -> dict:
        cols = self.source["kolumny"]
        rec = empty_record()
        uwagi: list[str] = []

        def col(key: str) -> str:
            name = cols.get(key)
            return normalize.clean_text(str(raw.get(name, ""))) if name else ""

        rec["id_zrodlowe"] = col("id")
        try:
            lat, lon, swapped = normalize.fix_coordinates(float(col("lat")), float(col("lon")))
            rec["szerokosc_geo"], rec["dlugosc_geo"] = f"{lat:.6f}", f"{lon:.6f}"
            if swapped:
                uwagi.append("współrzędne zamienione miejscami w źródle")
        except ValueError:
            uwagi.append("brak lub błędne współrzędne")

        if "adres" in cols:
            rec.update(normalize.parse_address(col("adres")))
        for key in ("ulica", "numer_budynku", "kod_pocztowy", "miejscowosc"):
            if key in cols:
                rec[key] = col(key)

        rec["nazwa_obiektu"] = _NAME_PREFIX.sub("", col("nazwa_obiektu")).strip()
        rec["telefon_kontaktowy"] = normalize.normalize_phone(col("telefon"))
        rec["zdjecie_url"] = _first_photo(raw) if cols.get("zdjecie") else ""

        # Pola, których źródło nie podaje – wartości „nieznane” dopuszczone przez schemat.
        rec["godziny_dostepnosci"] = "nieznane"
        rec["dostepny_24h"] = "nieznane"
        rec["status"] = "nieznany"
        rec["dostep"] = "nieznany"  # schemat v0.2: brak informacji to ostrzeżenie, nie odrzucenie rekordu
        rec["metoda_weryfikacji"] = "import"
        # Kto potwierdził lokalizację – tylko gdy rejestr źródeł mówi to wprost. Samo opublikowanie
        # zbioru nie jest potwierdzeniem, że urządzenie jest na miejscu.
        rec["lokalizacje_potwierdzil"] = self.source.get("lokalizacje_potwierdzil", "")

        rec["dysponent_nazwa"] = self.source["dysponent"]
        rec["zrodlo"] = self.id
        rec["licencja"] = self.source["licencja"]
        rec["data_weryfikacji"] = self._data_date()
        rec["data_aktualizacji"] = csvio.warsaw_now()  # czas polski bez strefy (#61)
        rec["id_aed"] = normalize.stable_id(self.id, rec["id_zrodlowe"])
        rec["_uwagi"] = uwagi
        return rec

    def _data_date(self) -> str:
        meta_path = self.raw_dir / "meta.json"
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            return (meta.get("data_date") or meta.get("modified") or "")[:10]
        return self.source.get("data_date", "")


def parse_csv(text: str) -> list[dict]:
    """CSV z dane.gov.pl, także w wariancie „cały wiersz w cudzysłowie” (Marki)."""
    rows = []
    for row in csv.reader(io.StringIO(text)):
        if len(row) == 1 and "," in row[0]:
            row = next(csv.reader(io.StringIO(row[0])))
        if any(cell.strip() for cell in row):
            rows.append([cell.strip() for cell in row])
    if not rows:
        return []
    header, *data = rows
    return [dict(zip(header, r)) for r in data]


def parse_geojson(text: str) -> list[dict]:
    out = []
    for feat in json.loads(text).get("features", []):
        props = dict(feat.get("properties") or {})
        geom = feat.get("geometry") or {}
        if geom.get("type") == "Point":
            props["_lon"], props["_lat"] = geom["coordinates"][:2]
        out.append(props)
    return out


def _first_photo(raw: dict) -> str:
    gallery = raw.get("gallery") or []
    return gallery[0].get("url", "") if gallery and isinstance(gallery[0], dict) else ""
