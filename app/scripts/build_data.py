"""Buduje app/data/aed-data.js z eksportu pipeline'u ingest/.

Uruchomienie (z katalogu głównego repo, po `python -m ingest fetch all && python -m ingest build all`):
    python app/scripts/build_data.py

Wejście: ingest/data/out/aed-app.geojson (lekki eksport dla app/, PR #26) – zawiera
status_weryfikacji, opis_weryfikacji i ten_sam_co. Rekordy z ten_sam_co (duplikat z OSM
AED-u, który ma już rekord zweryfikowany) pomijamy, żeby jeden AED nie był na mapie dwa razy.

Dane trafiają do pliku .js (a nie .json), żeby strona działała po otwarciu index.html
bezpośrednio z dysku – przeglądarki blokują fetch() plików lokalnych.

Format zwarty (~18 tys. AED, żeby plik nadawał się na telefon):
  slownik – lista wszystkich różnych tekstów (pozycja 0 = pusty tekst),
  pola    – nazwy pól w kolejności kolumn,
  aed     – wiersze [szer*1e5, dl*1e5, indeksy do słownika w kolejności pól...];
            końcowe puste pola są obcięte. Rozpakowuje AedCore.unpack().
Fikcyjnych rekordów przykładowych ze schema/ nie ma na stronie (decyzja Krystiana 21.11):
prawdziwe dane z OSM mają godziny, a fikcyjny AED na stronie ratunkowej mógłby mylić.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
INGEST_GEOJSON = REPO / "ingest" / "data" / "out" / "aed-app.geojson"
INGEST_FULL = REPO / "ingest" / "data" / "out" / "aed.geojson"
SOURCES = REPO / "ingest" / "sources.toml"
OUTPUT = REPO / "app" / "data" / "aed-data.js"

# Kolejność ma znaczenie dla rozmiaru: pola zawsze wypełnione na początku,
# rzadko wypełnione (adres jest prawie tylko w danych instytucji) na końcu.
PACKED_FIELDS = (
    "status_weryfikacji", "zrodlo", "licencja", "opis_weryfikacji", "status",
    "godziny_dostepnosci", "dostep", "opis_lokalizacji", "nazwa_obiektu", "dysponent_nazwa",
    "telefon_kontaktowy", "gmina", "wojewodztwo", "miejscowosc", "ulica", "numer_budynku", "kod_pocztowy",
)

# Pola z pełnego eksportu (aed.geojson), których nie ma w lekkim aed-app.geojson: gmina
# i województwo (przypisane z granic PRG) – do podpowiedzi w wyszukiwarce, bo adres ma
# tylko ok. 130 rekordów z OSM.
FULL_FIELDS = ("gmina", "wojewodztwo")



def pack_ingest() -> tuple[list[str], list[list[int]], int]:
    """Zwraca (słownik, wiersze, liczba pominiętych duplikatów)."""
    data = json.loads(INGEST_GEOJSON.read_text(encoding="utf-8"))
    full = {
        f["properties"]["id_aed"]: f["properties"]
        for f in json.loads(INGEST_FULL.read_text(encoding="utf-8"))["features"]
    }
    table: list[str] = [""]
    index = {"": 0}
    rows: list[list[int]] = []
    skipped = 0
    for feature in data["features"]:
        props = dict(feature["properties"])
        extra = full.get(props.get("id_aed"), {})
        for key in FULL_FIELDS:
            props.setdefault(key, extra.get(key, ""))
        if props.get("ten_sam_co"):
            skipped += 1
            continue
        lon, lat = feature["geometry"]["coordinates"]
        row = [round(lat * 1e5), round(lon * 1e5)]
        for key in PACKED_FIELDS:
            value = str(props.get(key) or "")
            if value not in index:
                index[value] = len(table)
                table.append(value)
            row.append(index[value])
        while len(row) > 2 and row[-1] == 0:
            row.pop()
        rows.append(row)
    # Stała kolejność (od północy) – powtarzalny wynik niezależnie od kolejności źródeł.
    rows.sort(key=lambda r: (-r[0], r[1]))
    return table, rows, skipped



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
    table, rows, skipped = pack_ingest()
    payload = {
        "wygenerowano": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "zrodla": load_sources(),
        "pola": list(PACKED_FIELDS),
        "slownik": table,
        "aed": rows,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    OUTPUT.write_text(
        "// Wygenerowano przez app/scripts/build_data.py – nie edytuj ręcznie.\n"
        f"window.AED_DATA={body};\n",
        encoding="utf-8",
    )
    size = OUTPUT.stat().st_size
    print(
        f"Zapisano {OUTPUT} ({len(rows)} AED, pominięto {skipped} duplikatów, "
        f"{size / 1e6:.1f} MB)"
    )


if __name__ == "__main__":
    main()
