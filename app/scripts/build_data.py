"""Buduje app/data/aed-data.js z wyniku pipeline'u ingest/ i przykładu ze schema/.

Uruchomienie (z katalogu głównego repo, po `python -m ingest fetch all && python -m ingest build all`):
    python app/scripts/build_data.py

Dane trafiają do pliku .js (a nie .json), żeby strona działała po otwarciu index.html
bezpośrednio z dysku – przeglądarki blokują fetch() plików lokalnych.
Do strony kopiujemy tylko pola potrzebne w interfejsie.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
INGEST_GEOJSON = REPO / "ingest" / "data" / "out" / "aed.geojson"
SCHEMA_EXAMPLE = REPO / "schema" / "przyklad-aed.csv"
SOURCES = REPO / "ingest" / "sources.toml"
OUTPUT = REPO / "app" / "data" / "aed-data.js"

FIELDS = (
    "id_aed", "nazwa_obiektu", "miejscowosc", "ulica", "numer_budynku", "kod_pocztowy",
    "opis_lokalizacji", "kondygnacja", "w_budynku", "dostep", "godziny_dostepnosci",
    "dostepny_24h", "status", "dysponent_nazwa", "telefon_kontaktowy", "data_weryfikacji",
    "zdjecie_url", "zrodlo", "licencja",
)


def slim(props: dict) -> dict:
    return {k: props.get(k, "") or "" for k in FIELDS}


def load_ingest() -> list[dict]:
    data = json.loads(INGEST_GEOJSON.read_text(encoding="utf-8"))
    out = []
    for feature in data["features"]:
        lon, lat = feature["geometry"]["coordinates"]
        rec = slim(feature["properties"])
        rec.update(lat=round(lat, 6), lon=round(lon, 6), przyklad=False)
        out.append(rec)
    return out


def load_examples() -> list[dict]:
    out = []
    with SCHEMA_EXAMPLE.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            rec = slim(row)
            rec.update(lat=float(row["szerokosc_geo"]), lon=float(row["dlugosc_geo"]), przyklad=True)
            out.append(rec)
    return out


def load_sources() -> list[dict]:
    """Źródła z ingest/sources.toml – do stopki z atrybucją (wymóg CC BY)."""
    import tomllib

    cfg = tomllib.loads(SOURCES.read_text(encoding="utf-8"))
    out = []
    for s in cfg.get("source", []):
        out.append(
            {
                "id": s.get("id", ""),
                "nazwa": s.get("nazwa", ""),
                "dysponent": s.get("dysponent", ""),
                "url": s.get("url", ""),
                "licencja": s.get("licencja", ""),
            }
        )
    return out


def main() -> None:
    records = load_ingest()
    payload = {
        "wygenerowano": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "zrodla": load_sources(),
        "aed": records,
        "przyklady": load_examples(),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, ensure_ascii=False, indent=1)
    OUTPUT.write_text(
        "// Wygenerowano przez app/scripts/build_data.py – nie edytuj ręcznie.\n"
        f"window.AED_DATA = {body};\n",
        encoding="utf-8",
    )
    print(f"Zapisano {OUTPUT} ({len(records)} AED, {len(payload['przyklady'])} przykładów)")


if __name__ == "__main__":
    main()
