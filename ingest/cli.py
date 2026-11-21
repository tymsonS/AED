"""CLI pipeline'u: python -m ingest <polecenie> [źródło|all]

  sources            lista źródeł z sources.toml
  fetch  <źródło>    pobiera surowe dane do ingest/data/raw/
  build  <źródło>    mapuje i normalizuje surowe dane, zapisuje ingest/data/out/
  validate           waliduje ingest/data/out/aed.csv względem schema/aed.schema.json
  package <źródło>   pakiet dostawcy dla dane.gov.pl (CSV, GeoJSON, XML harwestera, MD5)
  fetch-xsd          pobiera XSD harwestera z kodu portalu do ingest/data/xsd/
"""

from __future__ import annotations

import argparse
import csv
import sys
import tomllib
from pathlib import Path

from . import export, package, validate
from .adapters import ADAPTERS

HERE = Path(__file__).resolve().parent
SOURCES = HERE / "sources.toml"
DATA = HERE / "data"


def load_sources() -> list[dict]:
    with SOURCES.open("rb") as fh:
        return tomllib.load(fh)["source"]


def pick(sources: list[dict], name: str) -> list[dict]:
    if name == "all":
        return sources
    chosen = [s for s in sources if s["id"] == name]
    if not chosen:
        sys.exit(f"Nieznane źródło: {name}. Dostępne: {', '.join(s['id'] for s in sources)}")
    return chosen


def adapter_for(source: dict):
    return ADAPTERS[source["adapter"]](source, DATA / "raw")


def cmd_sources(_args) -> None:
    for s in load_sources():
        print(f"{s['id']:<24} poziom {s['poziom_zaufania']}  {s['dysponent']}  ({s['url']})")


def cmd_fetch(args) -> None:
    for s in pick(load_sources(), args.source):
        path = adapter_for(s).fetch()
        print(f"{s['id']}: pobrano {path}")


def load_records(name: str) -> list[dict]:
    records = []
    for s in pick(load_sources(), name):
        adapter = adapter_for(s)
        files = sorted(adapter.raw_dir.glob(f"resource-*.{s['format']}"))
        if not files:
            sys.exit(f"{s['id']}: brak surowych danych – najpierw: python -m ingest fetch {s['id']}")
        recs = adapter.records(files[-1])
        print(f"{s['id']}: {len(recs)} rekordów")
        records.extend(recs)
    return records


def cmd_build(args) -> None:
    records = load_records(args.source)
    out = DATA / "out"
    export.write_csv(records, out / "aed.csv")
    export.write_geojson(records, out / "aed.geojson")
    print(f"Zapisano {len(records)} rekordów do {out}")
    if validate.load_schema() is not None:
        _report(validate.validate(records), out)


def cmd_validate(_args) -> None:
    path = DATA / "out" / "aed.csv"
    with path.open(encoding="utf-8") as fh:
        records = list(csv.DictReader(fh))
    _report(validate.validate(records), DATA / "out")


def cmd_package(args) -> None:
    meta = package.PackageMeta(
        teryt=args.teryt, gmina=args.gmina, dostawca=args.dostawca, base_url=args.base_url,
        licencja=args.licencja, czestotliwosc=args.czestotliwosc, szkic=args.szkic,
    )
    out = DATA / "pakiety" / meta.ext_ident
    try:
        paths = package.write_package(load_records(args.source), meta, out)
    except package.PackageError as exc:
        sys.exit(f"Błąd pakietu: {exc}")
    print(f"Pakiet dostawcy zapisany w {out}:")
    for p in paths.values():
        print(f"  {p.name}")
    xsd = Path(args.xsd) if args.xsd else DATA / "xsd" / package.XSD_NAME
    if not xsd.exists():
        print(f"Bez walidacji XSD – brak {xsd}. Pobierz: python -m ingest fetch-xsd")
        return
    errors = package.validate_xml(paths["xml"], xsd)
    if errors:
        print(f"aed.xml NIEZGODNY ze schematem portalu ({len(errors)} błędów):")
        for e in errors[:10]:
            print(f"  - {e}")
        sys.exit(1)
    print(f"aed.xml zgodny ze schematem portalu {package.NAMESPACE}")


def cmd_fetch_xsd(_args) -> None:
    print(f"Pobieram kod portalu ({package.PORTAL_SOURCE_ZIP}, ok. 90 MB)…")
    print(f"Zapisano {package.fetch_xsd(DATA / 'xsd')}")


def _report(report: dict, out: Path) -> None:
    export.write_json(report, out / "validation_report.json")
    print(
        f"Walidacja: {report['rekordy']} rekordów, {report['rekordy_z_bledami']} z błędami, "
        f"{report['bledy']} błędów, {report['ostrzezenia']} ostrzeżeń -> {out / 'validation_report.json'}"
    )
    for field, count in list(report["problemy_wg_pola"].items())[:8]:
        print(f"  {field:<22} {count}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m ingest", description="Pipeline danych AED")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("sources").set_defaults(func=cmd_sources)
    for name, func in (("fetch", cmd_fetch), ("build", cmd_build)):
        p = sub.add_parser(name)
        p.add_argument("source", nargs="?", default="all")
        p.set_defaults(func=func)
    sub.add_parser("validate").set_defaults(func=cmd_validate)
    p = sub.add_parser("package", help="pakiet dostawcy dla dane.gov.pl")
    p.add_argument("source", help="id źródła z sources.toml albo all")
    p.add_argument("--teryt", required=True, help="kod TERYT obszaru (gmina: 7 cyfr TERC)")
    p.add_argument("--gmina", required=True, help="nazwa obszaru w tytule zbioru")
    p.add_argument("--dostawca", required=True, help="instytucja odpowiedzialna za zbiór")
    p.add_argument("--base-url", required=True, help="https://…/ – gdzie dostawca wystawi pliki")
    p.add_argument("--licencja", default="CC BY 4.0", choices=package.PORTAL_LICENSES)
    p.add_argument("--czestotliwosc", default="monthly", choices=package.UPDATE_FREQUENCIES)
    p.add_argument("--szkic", action="store_true", help="status draft zamiast published")
    p.add_argument("--xsd", help="ścieżka do XSD portalu (domyślnie ingest/data/xsd/)")
    p.set_defaults(func=cmd_package)
    sub.add_parser("fetch-xsd").set_defaults(func=cmd_fetch_xsd)
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
