"""Eksport do formatów odczytywalnych maszynowo: CSV (UTF-8, separator ,) i GeoJSON."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from .fields import field_names


def public(rec: dict) -> dict:
    """Rekord bez pól technicznych (zaczynających się od _)."""
    return {k: rec.get(k, "") for k in field_names()}


def write_csv(records: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(field_names()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(public(r) for r in records)


def write_geojson(records: list[dict], path: Path) -> None:
    features = []
    for rec in records:
        try:
            lon, lat = float(rec["dlugosc_geo"]), float(rec["szerokosc_geo"])
        except (KeyError, ValueError):
            continue
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": public(rec),
            }
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )


def app_properties(rec: dict, status: dict, dysponent_zrodla: str) -> dict:
    """Pola schematu + właściwości dla app/ spoza schematu wzorcowego.

    status_weryfikacji i opis_weryfikacji to tekst do pokazania obok koloru (WCAG 2.2 AA:
    informacja nie może być przekazana samym kolorem).
    """
    props = public(rec)
    props.update(status)
    if status["zweryfikowany"]:
        props["status_weryfikacji"] = "zweryfikowany"
        props["opis_weryfikacji"] = f"Dane instytucji: {dysponent_zrodla}."
    elif status["poza_obszarem_dysponenta"]:
        props["status_weryfikacji"] = "niezweryfikowany"
        props["opis_weryfikacji"] = (f"Opublikował {dysponent_zrodla}, ale punkt leży poza obszarem "
                                     "dysponenta – możliwy błąd w danych.")
    else:
        props["status_weryfikacji"] = "niezweryfikowany"
        props["opis_weryfikacji"] = (f"Dane społeczne – {dysponent_zrodla}. "
                                     "Żadna instytucja nie potwierdziła tego AED.")
    return props


def write_app_geojson(records: list[dict], statuses: list[dict], dysponenci: dict[str, str],
                      path: Path) -> int:
    """GeoJSON dla app/: wszystkie AED z poziomem zaufania i statusem weryfikacji.

    To nie jest plik wzorcowy – ma właściwości spoza schematu. Do publikacji na dane.gov.pl
    służą aed.csv / aed.geojson i pakiet dostawcy.
    """
    features = []
    for rec, status in zip(records, statuses, strict=True):
        try:
            lon, lat = float(rec["dlugosc_geo"]), float(rec["szerokosc_geo"])
        except (KeyError, ValueError):
            continue
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": app_properties(rec, status, dysponenci.get(rec["zrodlo"], rec["zrodlo"])),
        })
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False,
                   separators=(",", ":")),
        encoding="utf-8",
    )
    return len(features)


def write_json(data: dict | list, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
