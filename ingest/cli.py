"""CLI pipeline'u: python -m ingest <polecenie> [źródło|all]

  sources            lista źródeł z sources.toml
  fetch  <źródło>    pobiera surowe dane do ingest/data/raw/
  build  <źródło>    mapuje i normalizuje surowe dane, zapisuje ingest/data/out/
  validate           waliduje ingest/data/out/aed.csv względem schema/aed.schema.json
"""

from __future__ import annotations

import argparse
import csv
import sys
import tomllib
from pathlib import Path

from . import export, validate
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


def cmd_build(args) -> None:
    records = []
    for s in pick(load_sources(), args.source):
        adapter = adapter_for(s)
        files = sorted(adapter.raw_dir.glob(f"resource-*.{s['format']}"))
        if not files:
            sys.exit(f"{s['id']}: brak surowych danych – najpierw: python -m ingest fetch {s['id']}")
        recs = adapter.records(files[-1])
        print(f"{s['id']}: {len(recs)} rekordów")
        records.extend(recs)
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
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
