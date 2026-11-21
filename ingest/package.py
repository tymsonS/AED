"""Pakiet dostawcy: pliki, które gmina lub instytucja publikuje na dane.gov.pl.

Pakiet zawiera zasoby we wzorcowym zakresie danych (CSV, GeoJSON) oraz plik
harwestera XML według schematu portalu (urn:otwarte-dane:harvester:1.13) z sumą
kontrolną .md5. Wymagania opisuje docs/analiza-portalu-dane-gov-pl.md.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

from . import export, validate
from .fields import field_names

XSD_VERSION = "1.13"
NAMESPACE = f"urn:otwarte-dane:harvester:{XSD_VERSION}"
XSD_NAME = "xml_import_otwarte_dane_1_13.xsd"
PORTAL_SOURCE_ZIP = "https://dane.gov.pl/source-code/backend_latest.zip"

# Licencje dopuszczone przez portal (mcod/datasets/models.py) – ODbL nie ma.
PORTAL_LICENSES = (
    "CC0 1.0", "CC BY 4.0", "CC BY-SA 4.0", "CC BY-NC 4.0",
    "CC BY-NC-SA 4.0", "CC BY-ND 4.0", "CC BY-NC-ND 4.0",
)
_SPDX_TO_PORTAL = {
    "CC0-1.0": "CC0 1.0", "CC-BY-4.0": "CC BY 4.0", "CC-BY-SA-4.0": "CC BY-SA 4.0",
    "CC-BY-NC-4.0": "CC BY-NC 4.0", "CC-BY-NC-SA-4.0": "CC BY-NC-SA 4.0",
    "CC-BY-ND-4.0": "CC BY-ND 4.0", "CC-BY-NC-ND-4.0": "CC BY-NC-ND 4.0",
}
UPDATE_FREQUENCIES = (
    "daily", "weekly", "monthly", "quarterly", "everyHalfYear", "yearly", "irregular", "notPlanned",
)


class PackageError(ValueError):
    pass


@dataclass
class PackageMeta:
    teryt: str                      # kod TERYT gminy (TERC, 7 cyfr) albo powiatu/województwa
    gmina: str                      # nazwa obszaru w tytule zbioru
    dostawca: str                   # instytucja odpowiedzialna za zbiór
    base_url: str                   # https://…/ – adres, pod którym dostawca wystawi pliki
    licencja: str = "CC BY 4.0"
    czestotliwosc: str = "monthly"
    szkic: bool = False             # status="draft" zamiast "published"
    data_danych: str = field(default_factory=lambda: date.today().isoformat())

    def check(self) -> None:
        if not re.fullmatch(r"\d{2}|\d{4}|\d{7}", self.teryt):
            raise PackageError("TERYT musi mieć 2 (województwo), 4 (powiat) albo 7 cyfr (gmina, TERC)")
        if not self.base_url.startswith("https://"):
            raise PackageError("Portal przyjmuje tylko adresy https://")
        if self.licencja not in PORTAL_LICENSES:
            raise PackageError(f"Licencja spoza listy portalu: {self.licencja}. Dozwolone: {', '.join(PORTAL_LICENSES)}")
        if self.czestotliwosc not in UPDATE_FREQUENCIES:
            raise PackageError(f"Częstotliwość spoza listy portalu: {self.czestotliwosc}")
        if not self.base_url.endswith("/"):
            self.base_url += "/"

    @property
    def ext_ident(self) -> str:
        return f"aed-{self.teryt}"


def read_records_csv(path: Path) -> list[dict]:
    """Rekordy z pliku CSV we wzorcowym zakresie danych, np. potwierdzone.csv od dystrybutora
    (python -m ingest wczytaj-dystrybutora) albo plik przygotowany przez gminę."""
    try:
        with path.open(encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            missing = [f for f in field_names() if f not in (reader.fieldnames or [])]
            if missing:
                raise PackageError(f"{path.name}: brak kolumn wzorcowego zakresu danych: {', '.join(missing)}")
            records = [{k: (r.get(k) or "").strip() for k in field_names()} for r in reader]
    except UnicodeDecodeError as exc:
        raise PackageError(f"{path.name}: plik musi być w UTF-8") from exc
    for rec in records:
        rec["_uwagi"] = []
    return records


def filter_area(records: list[dict], teryt: str) -> tuple[list[dict], int]:
    """Rekordy z obszaru dostawcy (kod_teryt_gminy zaczyna się od kodu TERYT pakietu).

    Plik od dystrybutora może obejmować całe województwo, a gmina publikuje tylko swoje AED.
    Zwraca (rekordy z obszaru, liczba pominiętych – spoza obszaru albo bez kodu gminy).
    """
    inside = [r for r in records if r.get("kod_teryt_gminy", "").startswith(teryt)]
    return inside, len(records) - len(inside)


def check_licenses(records: list[dict]) -> None:
    """Pakiet może zawierać tylko dane na licencjach, które portal dopuszcza."""
    bad = sorted({r.get("licencja", "") for r in records if r.get("licencja", "") not in _SPDX_TO_PORTAL})
    if bad:
        raise PackageError(
            f"Rekordy na licencji spoza listy portalu ({', '.join(bad) or 'brak'}). "
            "Danych z OpenStreetMap (ODbL) nie publikujemy w pakiecie dostawcy."
        )


def build_xml(meta: PackageMeta, generated_at: datetime | None = None) -> bytes:
    """Plik harwestera XML zgodny ze schematem portalu 1.13."""
    meta.check()
    now = (generated_at or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    status = "draft" if meta.szkic else "published"
    root = ET.Element(f"{{{NAMESPACE}}}datasets")
    ds = ET.SubElement(root, "dataset", status=status)
    _text(ds, "extIdent", meta.ext_ident)
    _bilingual(ds, "title", f"Lokalizacje defibrylatorów AED – {meta.gmina}"[:300],
               f"AED defibrillator locations – {meta.gmina}"[:300])
    _bilingual(
        ds, "description",
        (f"Lokalizacje automatycznych defibrylatorów zewnętrznych (AED) na obszarze: {meta.gmina}. "
         f"Dostawca: {meta.dostawca}. Dane we wzorcowym zakresie danych o AED (akcja Misja AED, "
         "HackNation 2026): współrzędne WGS84, adres, dostępność, godziny, stan urządzenia, "
         "data weryfikacji.")[:1000],
        f"Automated external defibrillator (AED) locations in {meta.gmina}, in the model AED data scope."[:1000],
    )
    _text(ds, "updateFrequency", meta.czestotliwosc)
    cats = ET.SubElement(ds, "categories")
    _text(cats, "category", "HEAL")
    cond = ET.SubElement(ds, "conditions")
    _text(cond, "source", "true")
    _text(cond, "modification", "true")
    _text(cond, "responsibilities",
          f"{meta.dostawca} odpowiada za aktualność i poprawność danych o urządzeniach AED w zbiorze.")
    _text(cond, "dbOrCopyrighted", "Warunki wykorzystywania zgodnie z wybraną licencją.")
    _text(cond, "dbOrCopyrightedLicenseChosen", meta.licencja)
    _text(cond, "personalData", "Zbiór nie zawiera danych osobowych. Telefon kontaktowy to wyłącznie numer instytucji.")
    resources = ET.SubElement(ds, "resources")
    for ext, fmt_pl, fmt_en in (("csv", "CSV", "CSV"), ("geojson", "GeoJSON", "GeoJSON")):
        res = ET.SubElement(resources, "resource", status=status)
        _text(res, "extIdent", f"{meta.ext_ident}-{ext}")
        _text(res, "url", f"{meta.base_url}aed.{ext}")
        _bilingual(res, "title", f"Defibrylatory AED – {meta.gmina} ({fmt_pl})"[:300],
                   f"AED defibrillators – {meta.gmina} ({fmt_en})"[:300])
        _bilingual(res, "description",
                   f"Jeden wiersz to jedno urządzenie AED. Format {fmt_pl}, kodowanie UTF-8."[:1000],
                   f"One row per AED device. {fmt_en} format, UTF-8."[:1000])
        _text(res, "availability", "local")
        _text(res, "dataDate", meta.data_danych)
        _text(res, "lastUpdateDate", now)
        _text(res, "containsProtectedData", "false")
        regions = ET.SubElement(res, "regions")
        _text(regions, "terytIdent", meta.teryt)
    tags = ET.SubElement(ds, "tags")
    for tag in ("AED", "defibrylator", "pierwsza pomoc", "ratownictwo"):
        _text(tags, "tag", tag, lang="pl")
    _text(ds, "lastUpdateDate", now)
    for flag in ("hasDynamicData", "hasHighValueData", "hasHighValueDataFromEuropeanCommissionList", "hasResearchData"):
        _text(ds, flag, "false")

    ET.register_namespace("od", NAMESPACE)
    ET.indent(root)
    buf = io.BytesIO()
    ET.ElementTree(root).write(buf, encoding="UTF-8", xml_declaration=True)
    return buf.getvalue()


def write_package(records: list[dict], meta: PackageMeta, out_dir: Path) -> dict[str, Path]:
    meta.check()
    if not records:
        raise PackageError("Brak rekordów do pakietu")
    check_licenses(records)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "csv": out_dir / "aed.csv",
        "geojson": out_dir / "aed.geojson",
        "xml": out_dir / "aed.xml",
        "md5": out_dir / "aed.md5",
        "instrukcja": out_dir / "CZYTAJ-MNIE.txt",
    }
    if validate.load_schema() is not None:
        paths["raport"] = out_dir / "raport-walidacji.json"
        export.write_json(validate.validate(records), paths["raport"])
    export.write_csv(records, paths["csv"])
    export.write_geojson(records, paths["geojson"])
    xml = build_xml(meta)
    paths["xml"].write_bytes(xml)
    paths["md5"].write_text(hashlib.md5(xml).hexdigest() + "\n", encoding="ascii")
    paths["instrukcja"].write_text(_instructions(meta, len(records)), encoding="utf-8")
    return paths


def validate_xml(xml_path: Path, xsd_path: Path) -> list[str]:
    """Walidacja względem oryginalnego XSD portalu (wymaga biblioteki xmlschema)."""
    try:
        import xmlschema
    except ImportError as exc:
        raise PackageError("Walidacja XSD wymaga biblioteki xmlschema: pip install xmlschema") from exc
    schema = xmlschema.XMLSchema(str(xsd_path))
    return [str(err.reason or err) for err in schema.iter_errors(str(xml_path))]


def fetch_xsd(dest_dir: Path) -> Path:
    """Pobiera XSD harwestera z archiwum kodu portalu (GPL v3) do katalogu poza gitem."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    target = dest_dir / XSD_NAME
    zip_path = dest_dir / "backend_latest.zip"
    req = urllib.request.Request(PORTAL_SOURCE_ZIP, headers={"User-Agent": "misja-aed-ingest/0.1"})
    with urllib.request.urlopen(req, timeout=600) as resp, zip_path.open("wb") as fh:
        while chunk := resp.read(1 << 20):
            fh.write(chunk)
    with zipfile.ZipFile(zip_path) as zf:
        member = next(n for n in zf.namelist() if n.endswith(f"data/harvester/{XSD_NAME}"))
        target.write_bytes(zf.read(member))
    zip_path.unlink()
    return target


def _text(parent: ET.Element, tag: str, value: str, **attrs: str) -> ET.Element:
    el = ET.SubElement(parent, tag, **attrs)
    el.text = value
    return el


def _bilingual(parent: ET.Element, tag: str, polish: str, english: str) -> None:
    el = ET.SubElement(parent, tag)
    _text(el, "polish", polish)
    _text(el, "english", english)


def _instructions(meta: PackageMeta, count: int) -> str:
    return f"""Pakiet dostawcy danych AED – {meta.gmina}
Dostawca: {meta.dostawca}
Rekordów: {count}
Wygenerowano: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}

Pliki:
  aed.csv      – dane we wzorcowym zakresie (UTF-8, separator przecinek)
  aed.geojson  – te same dane jako mapa (WGS84)
  aed.xml      – opis zbioru dla harwestera dane.gov.pl (schemat {NAMESPACE})
  aed.md5      – suma kontrolna aed.xml, wymagana przez harwester
  raport-walidacji.json – braki i błędy względem wzorcowego zakresu danych

Zanim opublikujesz:
  1. Sprawdź każde urządzenie: czy jest na miejscu, czy działa, kiedy jest dostępne.
     Uzupełnij kolumny: dostep, godziny_dostepnosci, status, data_weryfikacji.
     Wpisz, kto potwierdził lokalizację (lokalizacje_potwierdzil, np. dystrybutor) i kto
     odpowiada za stan techniczny (odpowiedzialny_za_stan_techniczny; puste = dysponent).
     Tylko nazwy instytucji, bez danych osób. Lista braków jest w raport-walidacji.json.
  2. Po każdej zmianie aed.csv wygeneruj pakiet ponownie (zmieni się aed.md5).

Publikacja na dane.gov.pl – jeden z dwóch sposobów:
  A. Automatycznie: wystaw wszystkie pliki pod adresem {meta.base_url}
     i poproś administratora portalu o podłączenie źródła harwestera XML
     z adresem {meta.base_url}aed.xml. Portal będzie pobierał zmiany sam.
  B. Ręcznie: zaloguj się na dane.gov.pl, utwórz zbiór „Lokalizacje defibrylatorów AED – {meta.gmina}”
     w kategorii Zdrowie, dodaj aed.csv i aed.geojson jako zasoby, licencja {meta.licencja}.
     Przy aed.csv wskaż kolumny mapy: dlugosc_geo, szerokosc_geo, etykieta nazwa_obiektu.
"""
