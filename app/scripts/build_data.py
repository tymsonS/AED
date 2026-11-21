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
  kody    – stały kod każdego AED (10 znaków z id_aed), w kolejności wierszy – do adresu
            podstrony „Szczegóły” (aed.html?aed=…).
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
    "zdjecie_url",
)

# Pola z pełnego eksportu (aed.geojson), których nie ma w lekkim aed-app.geojson: gmina
# i województwo (przypisane z granic PRG) – do podpowiedzi w wyszukiwarce, bo adres ma
# tylko ok. 130 rekordów z OSM.
FULL_FIELDS = ("gmina", "wojewodztwo", "zdjecie_url")

# Zdjęcia pokazujemy tylko ze źródeł o znanych prawach:
# - OpenAEDMap – zdjęcia wgrywane z licencją CC0 (backend przyjmuje tylko CC0),
# - zbiór instytucji z dane.gov.pl – zdjęcie podał sam dysponent w swoim zbiorze.
# Inne adresy z tagu image w OSM (dowolne strony, skracacze linków, serwisy społecznościowe)
# pomijamy: nie znamy licencji i treści – strona pokaże wtedy „Brak zdjęcia”.
PHOTO_HOSTS = ("openaedmap.org", "back.openaedmap.org")


def photo_url(props: dict) -> str:
    from urllib.parse import urlparse

    url = props.get("zdjecie_url") or ""
    if not url.startswith("https://"):
        return ""
    if urlparse(url).netloc in PHOTO_HOSTS:
        return url
    if all(z.startswith("danegovpl-") for z in str(props.get("zrodlo", "")).split(";")):
        # Zdjęcie ze zbioru instytucji tylko, gdy adres wskazuje plik obrazu. Przemyśl podaje
        # przy każdym AED „/download/156869/<nazwa>” – serwer ignoruje końcówkę i zwraca ten
        # sam znak AED, a nie zdjęcie miejsca (review #47).
        if urlparse(url).path.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            return url
    return ""


def drop_shared_photos(features: list[dict]) -> int:
    """Ten sam adres zdjęcia przy kilku AED jednego źródła to nie zdjęcie miejsca (np. logo,
    znak AED) – usuwamy go. Zwraca liczbę wyczyszczonych rekordów."""
    from collections import Counter

    key = lambda p: (p.get("zrodlo", ""), p.get("zdjecie_url", ""))
    counts = Counter(key(p) for p in features if p.get("zdjecie_url"))
    dropped = 0
    for p in features:
        if p.get("zdjecie_url") and counts[key(p)] > 1:
            p["zdjecie_url"] = ""
            dropped += 1
    return dropped



KOD_LEN = 10


def code(id_aed: str) -> str:
    """Krótki, stały kod AED do adresu podstrony: 10 znaków szesnastkowych z id_aed (UUID v5
    z ingest/, ten sam przy każdym budowaniu). 18 tys. AED – szansa powtórzenia ok. 1:7 mln,
    a i tak sprawdzamy to przy budowaniu."""
    return id_aed.replace("-", "")[:KOD_LEN]


def pack_ingest() -> tuple[list[str], list[list[int]], list[str], int]:
    """Zwraca (słownik, wiersze, kody AED, liczba pominiętych duplikatów)."""
    data = json.loads(INGEST_GEOJSON.read_text(encoding="utf-8"))
    # Od #45/#49 lekki eksport ma gmina, wojewodztwo i zdjecie_url. Pełny aed.geojson (26 MB)
    # czytamy tylko wtedy, gdy któregoś z tych pól w lekkim pliku brakuje (starszy ingest/).
    first = data["features"][0]["properties"] if data["features"] else {}
    missing = [k for k in FULL_FIELDS if k not in first]
    full = {}
    if missing:
        print(f"aed-app.geojson bez pól {missing} – uzupełniam z aed.geojson")
        full = {
            f["properties"]["id_aed"]: f["properties"]
            for f in json.loads(INGEST_FULL.read_text(encoding="utf-8"))["features"]
        }
    table: list[str] = [""]
    index = {"": 0}
    rows: list[list[int]] = []
    skipped = 0
    merged = []
    for feature in data["features"]:
        props = dict(feature["properties"])
        extra = full.get(props.get("id_aed"), {})
        for key in missing:
            props[key] = extra.get(key, "")
        props["zdjecie_url"] = photo_url(props)
        merged.append((feature, props))
    drop_shared_photos([p for _, p in merged])
    for feature, props in merged:
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
        rows.append((row, code(props.get("id_aed", ""))))
    # Stała kolejność (od północy) – powtarzalny wynik niezależnie od kolejności źródeł.
    rows.sort(key=lambda r: (-r[0][0], r[0][1]))
    codes = [c for _, c in rows]
    if len(set(codes)) != len(codes):
        raise SystemExit("Powtórzony kod AED (10 znaków id_aed) – wydłuż KOD_LEN")
    return table, [r for r, _ in rows], codes, skipped



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
    table, rows, codes, skipped = pack_ingest()
    payload = {
        "wygenerowano": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "zrodla": load_sources(),
        "pola": list(PACKED_FIELDS),
        "slownik": table,
        "aed": rows,
        "kody": codes,
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
