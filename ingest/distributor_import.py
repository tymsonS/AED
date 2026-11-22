"""Wczytanie listy wypełnionej przez dystrybutora z powrotem do zbioru.

Dystrybutor dostaje do-potwierdzenia.csv (distributor.py), sprawdza AED w terenie i odsyła
plik. Tu zamieniamy potwierdzone wiersze na rekordy we wzorcowym zakresie danych:
metoda_weryfikacji = dystrybutor, lokalizacje_potwierdzil, data_weryfikacji = data_sprawdzenia.

Licencja (review #29): lista robocza miesza dane OSM (ODbL) z danymi instytucji. Do zbioru
na licencji Creative Commons z wiersza OSM bierzemy tylko to, co dystrybutor potwierdził
albo wpisał sam: lokalizację, daty, nazwy instytucji i nazwę obiektu własnymi słowami.
Nazwa, opis, adres, godziny i dostęp z OSM nie przechodzą – uzupełni je właściciel.
Wiersze instytucji (licencja CC) zachowują pola z oryginalnego rekordu.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from . import csvio, export, normalize, validate
from .distributor import KOLUMNY_DYSTRYBUTORA, WYNIKI
from .fields import empty_record
from .package import _SPDX_TO_PORTAL

# Licencje, z których rekord możemy przenieść do zbioru dostawcy (lista portalu).
CC_LICENSES = frozenset(_SPDX_TO_PORTAL)

# Pola, które dystrybutor wypełnia; reszta pliku to kontekst z listy roboczej.
# Kolumny dodane do listy później (#36, #42): listy rozesłane wcześniej ich nie mają, a muszą się
# wczytać – brak kolumny = pusta wartość (review #42).
OPTIONAL_COLUMNS = ("nazwa_obiektu_poprawiona", "poinformowano_dysponenta")
_REQUIRED_COLUMNS = ("id_aed", "zrodlo", "szerokosc_geo", "dlugosc_geo") + tuple(
    c for c in KOLUMNY_DYSTRYBUTORA if c not in OPTIONAL_COLUMNS)


class DistributorImportError(ValueError):
    pass


@dataclass
class ImportMeta:
    dystrybutor: str               # instytucja, która przysłała plik
    zrodlo: str = "dystrybutor"    # id źródła w zbiorze wynikowym
    licencja: str = "CC-BY-4.0"    # licencja SPDX zbioru wynikowego

    def check(self) -> None:
        if not self.dystrybutor.strip():
            raise DistributorImportError("Podaj nazwę dystrybutora")
        if not re.fullmatch(r"[a-z0-9_-]+", self.zrodlo):
            raise DistributorImportError(f"Identyfikator źródła {self.zrodlo!r}: tylko małe litery, cyfry, - i _")
        if self.licencja not in CC_LICENSES:
            raise DistributorImportError(f"Licencja {self.licencja!r} spoza listy portalu: {', '.join(sorted(CC_LICENSES))}")


def read_worklist(path: Path) -> list[dict]:
    """Czyta CSV po Excelu: UTF-8 (z BOM lub bez) albo Windows-1250, przecinek albo średnik."""
    rows = csvio.read_rows(path)
    missing = [c for c in _REQUIRED_COLUMNS if rows and c not in rows[0]]
    if not rows:
        raise DistributorImportError("Plik nie ma wierszy")
    if missing:
        raise DistributorImportError(f"Brak kolumn: {', '.join(missing)} – to nie jest lista z python -m ingest dystrybutor")
    # csvio.read_rows (#39) zwraca już przycięte wartości; brakujące kolumny opcjonalne = "" (#42).
    return [{c: "" for c in OPTIONAL_COLUMNS} | {k: _unescape(v) for k, v in r.items()} for r in rows]


def is_institution(zrodlo: str, institution_sources: set[str]) -> bool:
    """Czy rekord pochodzi z danych instytucji (np. zbioru gminy na dane.gov.pl).

    Jedna reguła dla wczytania listy i dla build (review #42): rekord instytucji ma w zrodlo
    źródło instytucji – poziom zaufania 1–2, ale nie „dystrybutor”. Kopia AED z OSM potwierdzona
    przez dystrybutora (zrodlo = dystrybutor) nie jest rekordem instytucji, więc przy zgłoszonym
    braku urządzenia znika od razu, tak jak wpis z OSM.
    """
    return any(part in institution_sources for part in zrodlo.split(";"))


def import_worklist(rows: list[dict], originals: dict[str, dict], meta: ImportMeta,
                    today: date | None = None, now: datetime | None = None,
                    institution_sources: set[str] | None = None) -> dict:
    """Zwraca potwierdzone rekordy, AED do usunięcia, pominięte wiersze i problemy.

    originals: id_aed -> rekord z pipeline'u (load_records), żeby sprawdzić, że wiersz
    pochodzi z naszej listy, i przenieść pola instytucji.
    institution_sources: id źródeł instytucji (CLI: z sources.toml); domyślnie – źródła
    rekordów na licencji z listy portalu, bez OSM.
    """
    if institution_sources is None:
        institution_sources = {o["zrodlo"] for o in originals.values() if o.get("licencja", "") in CC_LICENSES}
    meta.check()
    today = today or date.today()
    stamp = csvio.warsaw_now(now)  # data_aktualizacji: czas polski bez strefy (#61)
    confirmed, removed, skipped, problems = [], [], [], []

    def problem(i: int, row: dict, msg: str) -> None:
        problems.append({"wiersz": i, "id_aed": row.get("id_aed", ""), "komunikat": msg})

    seen: set[str] = set()
    for i, row in enumerate(rows, start=2):  # wiersz 1 to nagłówek, jak w Excelu
        result = row.get("wynik_sprawdzenia", "").lower()
        if result in ("", "nie_sprawdzono"):
            skipped.append(row.get("id_aed", ""))
            continue
        if result not in WYNIKI:
            problem(i, row, f"nieznany wynik_sprawdzenia {result!r} – dozwolone: {', '.join(WYNIKI)}")
            continue
        orig = originals.get(row.get("id_aed", ""))
        if orig is None or orig.get("zrodlo") != row.get("zrodlo"):
            problem(i, row, "id_aed lub zrodlo nie pasuje do żadnego AED z listy – wiersz zmieniony?")
            continue
        if row["id_aed"] in seen:
            problem(i, row, "ten sam AED drugi raz w pliku")
            continue
        seen.add(row["id_aed"])
        checked = _parse_date(row.get("data_sprawdzenia", ""))
        if checked is None or checked > today:
            problem(i, row, f"data_sprawdzenia {row.get('data_sprawdzenia', '')!r}: podaj datę RRRR-MM-DD, nie z przyszłości")
            continue
        if result == "brak_urzadzenia":
            informed_text = row.get("poinformowano_dysponenta", "")
            informed = _parse_date(informed_text) if informed_text else None
            if informed_text and (informed is None or informed > today or informed < checked):
                # Review #42: literówka nie może wyrzucić zgłoszenia. Zgłoszenie zostaje z pustą datą:
                # wpis OSM i tak znika, rekord instytucji zostaje oznaczony „do wyjaśnienia”.
                problem(i, row, f"poinformowano_dysponenta {informed_text!r}: podaj datę RRRR-MM-DD, nie wcześniejszą "
                                f"niż data_sprawdzenia ({checked.isoformat()}) i nie z przyszłości – zgłoszenie przyjęte "
                                "bez daty powiadomienia")
                informed = None
            if informed is None and is_institution(orig["zrodlo"], institution_sources):
                # Review #37: rekord instytucji usuwamy z naszych wyników dopiero po powiadomieniu dysponenta.
                problem(i, row, f"brak urządzenia w danych instytucji ({orig.get('dysponent_nazwa') or orig['zrodlo']}) – "
                                "najpierw poinformuj dysponenta i wpisz datę w poinformowano_dysponenta; "
                                "do tego czasu AED jest oznaczony „do wyjaśnienia z dysponentem”")
            removed.append({
                "id_aed": orig["id_aed"], "zrodlo": orig["zrodlo"], "id_zrodlowe": orig.get("id_zrodlowe", ""),
                "szerokosc_geo": orig.get("szerokosc_geo", ""), "dlugosc_geo": orig.get("dlugosc_geo", ""),
                "data_sprawdzenia": checked.isoformat(), "zglosil": meta.dystrybutor,
                "poinformowano_dysponenta": informed.isoformat() if informed else "",
                "uwagi_dystrybutora": row.get("uwagi_dystrybutora", ""),
            })
            continue
        coords = _coords(row, orig, result)
        if isinstance(coords, str):
            problem(i, row, coords)
            continue
        rec, notes = _record(row, orig, meta, checked, coords, stamp)
        for note in notes:
            problem(i, row, note)
        confirmed.append(rec)
    return {"potwierdzone": confirmed, "do_usuniecia": removed, "pominiete": skipped, "problemy": problems}


def merge_registered(old_rows: list[dict], new_rows: list[dict], reported: set[str]) -> list[dict]:
    """Scala wynik nowego wczytania z plikiem z poprzedniego wczytania tej samej listy (review #42).

    reported: id_aed, o których nowe wczytanie coś mówi (potwierdzone albo brak urządzenia).
    Stare wiersze o innych AED zostają, np. rekord gminy usunięty po powiadomieniu dysponenta
    nie trafia już na nową listę, a nie może wrócić na mapę. Przy braku urządzenia bez daty
    powiadomienia zachowujemy datę z poprzedniego wczytania.
    """
    old_by_id = {r["id_aed"]: r for r in old_rows}
    merged = [r for r in old_rows if r["id_aed"] not in reported]
    for row in new_rows:
        previous = old_by_id.get(row["id_aed"], {})
        if "poinformowano_dysponenta" in row and not row["poinformowano_dysponenta"]:
            row = dict(row, poinformowano_dysponenta=previous.get("poinformowano_dysponenta", ""))
        merged.append(row)
    return merged


def write_import(result: dict, meta: ImportMeta, out_dir: Path) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "csv": out_dir / "potwierdzone.csv",
        "geojson": out_dir / "potwierdzone.geojson",
        "usuniecia": out_dir / "do-usuniecia.csv",
        "raport": out_dir / "raport-wczytania.json",
    }
    export.write_csv(result["potwierdzone"], paths["csv"])
    export.write_geojson(result["potwierdzone"], paths["geojson"])
    cols = ("id_aed", "zrodlo", "id_zrodlowe", "szerokosc_geo", "dlugosc_geo",
            "data_sprawdzenia", "zglosil", "poinformowano_dysponenta", "uwagi_dystrybutora")
    with paths["usuniecia"].open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=cols, lineterminator="\n")
        writer.writeheader()
        writer.writerows(result["do_usuniecia"])
    report = validate.validate(result["potwierdzone"]) if validate.load_schema() is not None else None
    export.write_json({
        "dystrybutor": meta.dystrybutor,
        "zrodlo": meta.zrodlo,
        "licencja": meta.licencja,
        "potwierdzone": len(result["potwierdzone"]),
        "inne_miejsce": sum(r.get("_inne_miejsce", False) for r in result["potwierdzone"]),
        "do_usuniecia": len(result["do_usuniecia"]),
        "pominiete_niesprawdzone": len(result["pominiete"]),
        "problemy_wczytania": result["problemy"],
        "walidacja": None if report is None else {
            k: report[k] for k in ("rekordy", "rekordy_z_bledami", "bledy", "ostrzezenia", "problemy_wg_pola")
        },
    }, paths["raport"])
    return paths


def _record(row: dict, orig: dict, meta: ImportMeta, checked: date, coords: tuple[float, float],
            stamp: str) -> tuple[dict, list[str]]:
    notes = []
    from_institution = orig.get("licencja", "") in CC_LICENSES
    rec = dict(orig) if from_institution else empty_record()
    rec.pop("_uwagi", None)
    rec["id_aed"] = orig["id_aed"]
    # Rekord instytucji zachowuje swój identyfikator (np. „17” z Krosna); z OSM nie bierzemy
    # identyfikatora węzła jako treści, więc id_zrodlowe = id_aed (review #36).
    rec["id_zrodlowe"] = orig.get("id_zrodlowe", "") if from_institution else orig["id_aed"]
    rec["szerokosc_geo"], rec["dlugosc_geo"] = f"{coords[0]:.6f}", f"{coords[1]:.6f}"
    moved = coords != _orig_coords(orig)
    # Gminę i województwo wyliczamy sami z granic PRG (nie z OSM). Po zmianie miejsca – od nowa (CLI).
    for key in ("wojewodztwo", "powiat", "gmina", "kod_teryt_gminy"):
        rec[key] = "" if moved else orig.get(key, "")
    if not from_institution:
        # Z OSM nic poza lokalizacją – reszta „nieznana” do czasu danych od właściciela.
        rec.update(dostep="nieznany", godziny_dostepnosci="nieznane", dostepny_24h="nieznane", status="nieznany")
    rec["_inne_miejsce"] = moved

    name = row.get("nazwa_obiektu_poprawiona", "")
    if name:
        rec["nazwa_obiektu"] = name
    elif not from_institution:
        notes.append("wiersz z OpenStreetMap bez nazwa_obiektu_poprawiona – nazwy z OSM nie publikujemy")
    owner = row.get("dysponent_poprawiony", "")
    if owner:
        rec["dysponent_nazwa"] = owner
    elif not from_institution:
        notes.append("wiersz z OpenStreetMap bez dysponent_poprawiony – dysponenta z OSM nie publikujemy")

    rec["lokalizacje_potwierdzil"] = row.get("lokalizacje_potwierdzil", "") or meta.dystrybutor
    if not row.get("lokalizacje_potwierdzil"):
        notes.append(f"puste lokalizacje_potwierdzil – wpisano dystrybutora: {meta.dystrybutor}")
    rec["odpowiedzialny_za_stan_techniczny"] = row.get("odpowiedzialny_za_stan_techniczny", "")
    rec["data_weryfikacji"] = checked.isoformat()
    rec["metoda_weryfikacji"] = "dystrybutor"
    # Rekord instytucji zachowuje swoje źródło (schemat: kilka id rozdzielonych „;”).
    # Z wiersza OSM nie bierzemy treści, więc źródłem jest tylko dystrybutor.
    rec["zrodlo"] = f"{orig['zrodlo']};{meta.zrodlo}" if from_institution else meta.zrodlo
    rec["licencja"] = orig["licencja"] if from_institution else meta.licencja
    rec["data_aktualizacji"] = stamp
    return rec, notes


def _coords(row: dict, orig: dict, result: str) -> tuple[float, float] | str:
    try:
        lat, lon = float(row["szerokosc_geo"].replace(",", ".")), float(row["dlugosc_geo"].replace(",", "."))
    except ValueError:
        return "niepoprawne współrzędne"
    lat, lon, _ = normalize.fix_coordinates(lat, lon)
    if not normalize.in_poland(lat, lon):
        return "współrzędne poza Polską"
    lat, lon = round(lat, 6), round(lon, 6)
    if result == "inne_miejsce" and (lat, lon) == _orig_coords(orig):
        return "wynik inne_miejsce, ale współrzędne bez zmian – wpisz nowe w szerokosc_geo i dlugosc_geo"
    return lat, lon


def _orig_coords(orig: dict) -> tuple[float, float] | None:
    try:
        return round(float(orig["szerokosc_geo"]), 6), round(float(orig["dlugosc_geo"]), 6)
    except (KeyError, ValueError):
        return None


def _parse_date(text: str) -> date | None:
    return csvio.parse_date(text)


def _unescape(value: str) -> str:
    """Zdejmuje apostrof, który excel_safe() dodał przed znakiem formuły."""
    if value.startswith("'") and value[1:2] in ("=", "+", "-", "@", "\t", "\r"):
        return value[1:]
    return value
