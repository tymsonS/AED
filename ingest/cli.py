"""CLI pipeline'u: python -m ingest <polecenie> [źródło|all]

  sources            lista źródeł z sources.toml
  fetch  <źródło>    pobiera surowe dane do ingest/data/raw/
  build  <źródło>    mapuje i normalizuje surowe dane, zapisuje ingest/data/out/
                     (aed.csv, aed.geojson – wzorcowe; aed-app.geojson – dla app/)
  validate           waliduje ingest/data/out/aed.csv względem schema/aed.schema.json
  package <źródło>   pakiet dostawcy dla dane.gov.pl (CSV, GeoJSON, XML harwestera, MD5)
  fetch-xsd          pobiera XSD harwestera z kodu portalu do ingest/data/xsd/
  fetch-gminy        pobiera granice gmin z PRG (GUGiK) do ingest/data/prg/
  dystrybutor        lista AED do potwierdzenia na obszarze dystrybutora (ingest/data/pakiety/)
  stats              statystyki do prezentacji (ingest/data/out/statystyki.json, .md)
  gaps               mapa luk: stan danych o AED w każdej gminie (ingest/data/out/mapa-luk.*)
"""

from __future__ import annotations

import argparse
import csv
import sys
import tomllib
from pathlib import Path

import json

from . import distributor, export, gaps, gminy, package, stats, validate
from .adapters import ADAPTERS

HERE = Path(__file__).resolve().parent
SOURCES = HERE / "sources.toml"
DATA = HERE / "data"
GMINY = DATA / "prg" / "gminy.json"


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
    if GMINY.exists():
        enrich_records(records)
    else:
        # Bez granic gmin nie wykryjemy AED poza obszarem dysponenta – taki punkt (np. AED z Marek
        # ze współrzędnymi w Krośnie) dostałby status „zweryfikowany” w aed-app.geojson (review #32).
        print("UWAGA: brak granic gmin – AED poza obszarem dysponenta nie są wykrywane, a rekordy bez "
              "gminy i województwa. Pobierz raz: python -m ingest fetch-gminy", file=sys.stderr)
    return records


def enrich_records(records: list[dict]) -> None:
    """Przypisuje AED do gmin (TERYT) i oznacza punkty poza obszarem dysponenta."""
    index = gminy.GminaIndex.load(GMINY)
    hit = gminy.enrich(records, index)
    print(f"Przypisano do gmin: {hit} z {len(records)}")
    source_teryt = {s["id"]: s["teryt"] for s in load_sources() if s.get("teryt")}
    for rec in gaps.outside_publisher_area(records, source_teryt):
        rec.setdefault("_uwagi", []).append(
            f"{gaps.OUTSIDE_NOTE}: punkt w gminie {rec['gmina']} ({rec['kod_teryt_gminy']})"
        )


def cmd_build(args) -> None:
    records = load_records(args.source)
    out = DATA / "out"
    export.write_csv(records, out / "aed.csv")
    export.write_geojson(records, out / "aed.geojson")
    print(f"Zapisano {len(records)} rekordów do {out}")
    write_app_export(records, out)
    if validate.load_schema() is not None:
        _report(validate.validate(records), out)


def write_app_export(records: list[dict], out: Path) -> None:
    """aed-app.geojson: AED z poziomem zaufania i statusem weryfikacji dla app/ (poza schematem)."""
    sources = load_sources()
    trust = {s["id"]: s["poziom_zaufania"] for s in sources}
    statuses = gaps.verification(records, trust)
    n = export.write_app_geojson(records, statuses, {s["id"]: s["dysponent"] for s in sources},
                                 out / "aed-app.geojson")
    ver = sum(st["zweryfikowany"] for st in statuses)
    dup = sum(bool(st["ten_sam_co"]) for st in statuses)
    print(f"Eksport dla app/: {n} AED ({ver} zweryfikowanych, {dup} punktów OSM to ten sam AED "
          f"co zweryfikowany) -> {out / 'aed-app.geojson'}")


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


def cmd_dystrybutor(args) -> None:
    if not GMINY.exists():
        sys.exit("Lista dla dystrybutora wymaga granic gmin – najpierw: python -m ingest fetch-gminy")
    meta = distributor.DistributorMeta(obszar=args.obszar, dystrybutor=args.dystrybutor,
                                       nazwa_obszaru=args.nazwa or "")
    try:
        meta.check()
    except distributor.DistributorError as exc:
        sys.exit(f"Błąd: {exc}")
    records = load_records("all")
    trust = {s["id"]: s["poziom_zaufania"] for s in load_sources()}
    try:
        out = DATA / "pakiety" / meta.ident
        paths = distributor.write_distributor_package(records, gaps.verification(records, trust), meta, out)
    except distributor.DistributorError as exc:
        sys.exit(f"Błąd: {exc}")
    summ = json.loads(paths["podsumowanie"].read_text(encoding="utf-8"))
    print(f"Lista dla dystrybutora ({meta.nazwa_obszaru}) w {out}:")
    for p in paths.values():
        print(f"  {p.name}")
    print(f"  AED do sprawdzenia: {summ['aed_do_sprawdzenia']} (zweryfikowane: {summ['zweryfikowane']}, "
          f"pominięte duplikaty OSM: {summ['pominiete_duplikaty_osm']})")
    for label, n in summ["wg_priorytetu"].items():
        print(f"    {label}: {n}")


def cmd_fetch_xsd(_args) -> None:
    print(f"Pobieram kod portalu ({package.PORTAL_SOURCE_ZIP}, ok. 90 MB)…")
    print(f"Zapisano {package.fetch_xsd(DATA / 'xsd')}")


def cmd_fetch_gminy(_args) -> None:
    print(f"Pobieram granice gmin z PRG ({gminy.WFS_URL})…")
    print(f"Zapisano {gminy.fetch_gminy(GMINY)}")


def cmd_gaps(_args) -> None:
    if not GMINY.exists():
        sys.exit("Brak granic gmin – najpierw: python -m ingest fetch-gminy")
    sources = load_sources()
    records = load_records("all")
    gm = json.loads(GMINY.read_text(encoding="utf-8"))
    trust = {s["id"]: s["poziom_zaufania"] for s in sources}
    publishers = {s["teryt"]: s["id"] for s in sources if s.get("teryt")}
    rows = gaps.build_gaps(records, gm, trust, publishers)
    out = DATA / "out"
    with (out / "mapa-luk.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    by_teryt = {r["kod_teryt_gminy"]: r for r in rows}
    features = [
        {
            "type": "Feature",
            "geometry": {"type": "MultiPolygon", "coordinates": [
                [gminy.simplify(ring, 0.003) for ring in poly] for poly in g["polygons"]
            ]},
            "properties": by_teryt[g["teryt"]],
        }
        for g in gm
    ]
    (out / "mapa-luk.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    summ = gaps.summary(rows)
    export.write_json(summ, out / "mapa-luk-podsumowanie.json")
    print(f"Mapa luk: {summ['gminy']} gmin -> {out / 'mapa-luk.csv'}, mapa-luk.geojson, mapa-luk-podsumowanie.json")
    for status, n in sorted(summ["gminy_wg_statusu"].items(), key=lambda kv: -kv[1]):
        print(f"  {status:<32} {n}")
    print(f"  AED zweryfikowane: {summ['aed_zweryfikowane']}, niezweryfikowane: {summ['aed_niezweryfikowane']}")


def cmd_stats(_args) -> None:
    sources = load_sources()
    records = load_records("all")
    trust = {s["id"]: s["poziom_zaufania"] for s in sources}
    gap_rows = None
    if GMINY.exists():
        publishers = {s["teryt"]: s["id"] for s in sources if s.get("teryt")}
        gap_rows = gaps.build_gaps(records, json.loads(GMINY.read_text(encoding="utf-8")), trust, publishers)
    else:
        print("Bez pokrycia gmin – brak granic. Pobierz: python -m ingest fetch-gminy")
    report = validate.validate(records) if validate.load_schema() is not None else None
    result = stats.compute(records, gaps.verification(records, trust), sources, gap_rows, report)
    out = DATA / "out"
    export.write_json(result, out / "statystyki.json")
    (out / "statystyki.md").write_text(stats.render_md(result), encoding="utf-8")
    print(f"Statystyki: {result['aed']} AED, {result['aed_zweryfikowane']} zweryfikowanych "
          f"-> {out / 'statystyki.json'}, statystyki.md")


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
    p = sub.add_parser("dystrybutor", help="lista AED do potwierdzenia dla dystrybutora")
    p.add_argument("--obszar", required=True, nargs="+",
                   help="kody TERYT: 2 cyfry (województwo), 4 (powiat), 7 (gmina); można podać kilka")
    p.add_argument("--dystrybutor", required=True, help="instytucja, która potwierdza lokalizacje")
    p.add_argument("--nazwa", help="nazwa obszaru w plikach (domyślnie z kodów TERYT)")
    p.set_defaults(func=cmd_dystrybutor)
    sub.add_parser("fetch-xsd").set_defaults(func=cmd_fetch_xsd)
    sub.add_parser("fetch-gminy").set_defaults(func=cmd_fetch_gminy)
    sub.add_parser("gaps", help="mapa luk po gminach").set_defaults(func=cmd_gaps)
    sub.add_parser("stats", help="statystyki do prezentacji").set_defaults(func=cmd_stats)
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
