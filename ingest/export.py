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


def write_json(data: dict | list, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
