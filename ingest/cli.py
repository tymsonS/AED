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
  wczytaj-dystrybutora <plik>  wczytuje listę wypełnioną przez dystrybutora (potwierdzone AED)
  stats              statystyki do prezentacji (ingest/data/out/statystyki.json, .md)
  gaps               mapa luk: stan danych o AED w każdej gminie (ingest/data/out/mapa-luk.*)
"""

from __future__ import annotations

import argparse
import csv
import shutil
import sys
import tomllib
from pathlib import Path

import json

from . import distributor, distributor_import, export, gaps, gminy, package, stats, validate
from .adapters import ADAPTERS, LOCAL_ADAPTERS

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
        if s["adapter"] in LOCAL_ADAPTERS:
            print(f"{s['id']}: źródło lokalne – nic do pobrania")
            continue
        path = adapter_for(s).fetch()
        print(f"{s['id']}: pobrano {path}")


def load_records(name: str, distributor_sources: bool = True) -> list[dict]:
    """Rekordy ze źródeł. distributor_sources=False – bez AED potwierdzonych przez dystrybutora
    (wczytaj-dystrybutora porównuje listę z danymi, z których ją zbudowano)."""
    sources = load_sources()
    trust = {s["id"]: s["poziom_zaufania"] for s in sources}
    records, missing = [], {}
    for s in pick(sources, name):
        if s["adapter"] == "dystrybutor" and not distributor_sources:
            continue
        adapter = adapter_for(s)
        files = sorted(adapter.raw_dir.glob(f"resource-*.{s['format']}"))
        if not files:
            if s.get("opcjonalne"):
                continue  # np. brak wczytanych list dystrybutora – to nie błąd
            sys.exit(f"{s['id']}: brak surowych danych – najpierw: python -m ingest fetch {s['id']}")
        # Źródło z wieloma plikami (jedna lista na obszar dystrybutora) czytamy w całości.
        recs = [r for f in (files if s.get("wszystkie_pliki") else files[-1:]) for r in adapter.records(f)]
        print(f"{s['id']}: {len(recs)} rekordów")
        records.extend(recs)
        if hasattr(adapter, "missing_reports"):
            missing.update(adapter.missing_reports())
    if missing:
        records = _apply_missing_reports(records, missing, _institution_sources())
    records, replaced = gaps.supersede(records, trust)
    if replaced:
        print(f"Zastąpione rekordami potwierdzonymi przez dystrybutora: {replaced}")
    if GMINY.exists():
        enrich_records(records)
    else:
        # Bez granic gmin nie wykryjemy AED poza obszarem dysponenta – taki punkt (np. AED z Marek
        # ze współrzędnymi w Krośnie) dostałby status „zweryfikowany” w aed-app.geojson (review #32).
        print("UWAGA: brak granic gmin – AED poza obszarem dysponenta nie są wykrywane, a rekordy bez "
              "gminy i województwa. Pobierz raz: python -m ingest fetch-gminy", file=sys.stderr)
    return records


def _apply_missing_reports(records: list[dict], missing: dict[str, dict],
                           institution_sources: set[str]) -> list[dict]:
    """AED, których dystrybutor nie znalazł na miejscu (review #37).

    1. Wpis społeczny (OSM) usuwamy z naszych wyników od razu.
    2. Rekord instytucji – dopiero gdy dystrybutor wpisał datę poinformowania dysponenta
       (poinformowano_dysponenta). Za powiadomienie odpowiada dystrybutor.
    3. Bez tej daty rekord instytucji zostaje oznaczony „zgłoszony brak urządzenia, do wyjaśnienia
       z dysponentem”: przestaje być zweryfikowany, a na liście dla dystrybutora ma priorytet 1.
    Zbiór instytucji na dane.gov.pl poprawia jego właściciel; gdy to zrobi, rekord zniknie
    przy kolejnym fetch.
    """
    kept, dropped, informed, flagged = [], 0, 0, 0
    for rec in records:
        report = missing.get(rec.get("id_aed", ""))
        if report is None:
            kept.append(rec)
        elif not distributor_import.is_institution(rec["zrodlo"], institution_sources):
            dropped += 1
        elif report["poinformowano"]:
            informed += 1
        else:
            rec["_zgloszony_brak"] = report["opis"]
            rec.setdefault("_uwagi", []).append(
                f"zgłoszony brak urządzenia ({report['opis']}) – do wyjaśnienia z dysponentem")
            kept.append(rec)
            flagged += 1
    print(f"Zgłoszony brak urządzenia: {dropped} wpisów społecznych pominiętych, {informed} rekordów instytucji "
          f"pominiętych po powiadomieniu dysponenta, {flagged} oznaczonych do wyjaśnienia z dysponentem")
    return kept


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
    if bool(args.source) == bool(args.plik):
        sys.exit("Podaj id źródła z sources.toml albo --plik <csv> (jedno z dwóch)")
    out = DATA / "pakiety" / meta.ext_ident
    try:
        meta.check()
        if args.plik:
            every = package.read_records_csv(Path(args.plik), default_source=package.DEFAULT_FILE_SOURCE)
            _fill_teryt(every, meta.teryt)
            records, outside = package.filter_area(every, meta.teryt)
            print(f"{Path(args.plik).name}: {len(records)} rekordów z obszaru {meta.teryt}"
                  + (f", pominięte spoza obszaru: {outside}" if outside else ""))
        else:
            records = load_records(args.source)
        paths = package.write_package(records, meta, out)
    except package.PackageError as exc:
        sys.exit(f"Błąd pakietu: {exc}")
    print(f"Pakiet dostawcy zapisany w {out}:")
    for p in paths.values():
        print(f"  {p.name}")
    if "raport" in paths:
        rep = json.loads(paths["raport"].read_text(encoding="utf-8"))
        print(f"Walidacja: {rep['rekordy']} rekordów, {rep['rekordy_z_bledami']} z błędami, "
              f"{rep['ostrzezenia']} ostrzeżeń – szczegóły w {paths['raport'].name}")
        has_errors = rep["rekordy_z_bledami"] > 0
    else:
        has_errors = False
    xsd = Path(args.xsd) if args.xsd else DATA / "xsd" / package.XSD_NAME
    if not xsd.exists():
        # Bez XSD nie kończymy wcześniej – błędy walidacji rekordów i tak dają kod 1 (review #39).
        print(f"Bez walidacji XSD – brak {xsd}. Pobierz: python -m ingest fetch-xsd")
    else:
        errors = package.validate_xml(paths["xml"], xsd)
        if errors:
            print(f"aed.xml NIEZGODNY ze schematem portalu ({len(errors)} błędów):")
            for e in errors[:10]:
                print(f"  - {e}")
            sys.exit(1)
        print(f"aed.xml zgodny ze schematem portalu {package.NAMESPACE}")
    if has_errors:
        # Pliki zostają do poprawy, ale skrypt (np. CI) ma widzieć, że pakiet nie nadaje się do publikacji.
        sys.exit("UWAGA: pakiet ma rekordy z błędami walidacji – popraw je przed publikacją (raport-walidacji.json).")


def _fill_teryt(records: list[dict], teryt: str) -> None:
    """Rekordy pliku bez kod_teryt_gminy (kolumna w schemacie jest opcjonalna, review #39):
    1. z granic PRG, gdy są pobrane (tak jak w build);
    2. bez granic: pakiet dla jednej gminy (7 cyfr) – kod z --teryt, z uwagą;
    3. inaczej czytelny błąd – nie wiadomo, do której gminy należy AED.
    """
    lacking = [r for r in records if not r.get("kod_teryt_gminy")]
    if not lacking:
        return
    if GMINY.exists():
        hit = gminy.enrich(lacking, gminy.GminaIndex.load(GMINY))
        print(f"Kod gminy z granic PRG: {hit} z {len(lacking)} rekordów bez kod_teryt_gminy")
        lacking = [r for r in lacking if not r.get("kod_teryt_gminy")]
    if lacking and len(teryt) == 7:
        for rec in lacking:
            rec["kod_teryt_gminy"] = teryt
            rec["_uwagi"].append(f"brak kod_teryt_gminy – przyjęto gminę pakietu {teryt}")
        print(f"Kod gminy z --teryt: {len(lacking)} rekordów (bez granic PRG nie da się sprawdzić położenia)")
    elif lacking:
        sys.exit(f"Błąd pakietu: {len(lacking)} rekordów bez kod_teryt_gminy, a pakiet obejmuje więcej niż jedną "
                 f"gminę ({teryt}). Uzupełnij kolumnę albo pobierz granice gmin: python -m ingest fetch-gminy")


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


def cmd_wczytaj_dystrybutora(args) -> None:
    src = Path(args.plik)
    if not src.exists():
        sys.exit(f"Brak pliku {src}")
    meta = distributor_import.ImportMeta(dystrybutor=args.dystrybutor, zrodlo=args.zrodlo, licencja=args.licencja)
    try:
        meta.check()
        rows = distributor_import.read_worklist(src)
    except distributor_import.DistributorImportError as exc:
        sys.exit(f"Błąd: {exc}")
    # Porównujemy z danymi, z których zbudowano listę – bez wcześniej wczytanych potwierdzeń.
    originals = {r["id_aed"]: r for r in load_records("all", distributor_sources=False)}
    result = distributor_import.import_worklist(rows, originals, meta, institution_sources=_institution_sources())
    moved = [r for r in result["potwierdzone"] if r.get("_inne_miejsce")]
    if moved and GMINY.exists():
        gminy.enrich(moved, gminy.GminaIndex.load(GMINY))
    out = src.parent / "wczytane"
    paths = distributor_import.write_import(result, meta, out)
    report = json.loads(paths["raport"].read_text(encoding="utf-8"))
    registered = _register_distributor_files(paths, meta.zrodlo, src.parent.name, meta.dystrybutor)
    print(f"Wczytano {src.name} -> {out}:")
    for p in paths.values():
        print(f"  {p.name}")
    print(f"  potwierdzone: {report['potwierdzone']} (w innym miejscu: {report['inne_miejsce']}), "
          f"do usunięcia: {report['do_usuniecia']}, niesprawdzone: {report['pominiete_niesprawdzone']}, "
          f"problemy: {len(report['problemy_wczytania'])}")
    for p in report["problemy_wczytania"][:10]:
        print(f"    wiersz {p['wiersz']}: {p['komunikat']}")
    if registered:
        print(f"Źródło {meta.zrodlo}: {registered}. Po python -m ingest build all potwierdzone AED "
              "będą zweryfikowane w mapie luk, statystykach i aed-app.geojson.")
    else:
        print(f"Źródła {meta.zrodlo!r} nie ma w sources.toml z adapterem dystrybutor – wynik nie trafi do build.")


def _institution_sources() -> set[str]:
    """Źródła instytucji: poziom zaufania 1–2, bez źródeł dystrybutora (distributor_import.is_institution)."""
    return {s["id"] for s in load_sources() if s["poziom_zaufania"] <= 2 and s["adapter"] != "dystrybutor"}


def _register_distributor_files(paths: dict, zrodlo: str, ident: str, dystrybutor: str) -> str:
    """Kopiuje wynik do raw/<zrodlo>/, skąd czyta go adapter dystrybutor.

    Nazwa pliku = obszar + dystrybutor (review #37): ponowne wczytanie listy tego samego
    dystrybutora dla tego samego obszaru zastępuje poprzednie, a listy dwóch dystrybutorów
    z jednego obszaru się nie nadpisują.
    """
    source = next((s for s in load_sources() if s["id"] == zrodlo and s["adapter"] == "dystrybutor"), None)
    if source is None:
        return ""
    raw = DATA / "raw" / zrodlo
    raw.mkdir(parents=True, exist_ok=True)
    name = f"{ident}--{distributor.slug(dystrybutor)}"
    # Review #42: nie nadpisujemy poprzedniego wczytania tej samej listy, tylko scalamy – inaczej
    # AED usunięty po powiadomieniu (już nie na liście) wróciłby na mapę, a potwierdzenie AED
    # zostawionego pustym na nowej liście by przepadło.
    new_confirmed, new_removed = _read_csv(paths["csv"]), _read_csv(paths["usuniecia"])
    reported = {r["id_aed"] for r in new_confirmed + new_removed}
    for target, new_rows, src in ((raw / f"resource-{name}.csv", new_confirmed, paths["csv"]),
                                  (raw / f"usuniete-{name}.csv", new_removed, paths["usuniecia"])):
        merged = distributor_import.merge_registered(_read_csv(target), new_rows, reported)
        _write_csv_like(src, target, merged)
    return f"zapisano raw/{zrodlo}/resource-{name}.csv i usuniete-{name}.csv"


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _write_csv_like(template: Path, target: Path, rows: list[dict]) -> None:
    """Zapisuje rows w układzie kolumn pliku template (UTF-8, przecinek)."""
    with template.open(encoding="utf-8", newline="") as fh:
        columns = next(csv.reader(fh))
    with target.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


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
    p.add_argument("source", nargs="?", help="id źródła z sources.toml albo all")
    p.add_argument("--plik", help="zamiast źródła: CSV we wzorcowym zakresie, np. wczytane/potwierdzone.csv; "
                                  "do pakietu trafiają tylko AED z obszaru --teryt")
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
    p = sub.add_parser("wczytaj-dystrybutora", help="wczytuje listę wypełnioną przez dystrybutora")
    p.add_argument("plik", help="do-potwierdzenia.csv po wypełnieniu (CSV z Excela też)")
    p.add_argument("--dystrybutor", required=True, help="instytucja, która przysłała plik")
    p.add_argument("--zrodlo", default="dystrybutor", help="id źródła w zbiorze wynikowym")
    p.add_argument("--licencja", default="CC-BY-4.0", help="licencja SPDX zbioru wynikowego")
    p.set_defaults(func=cmd_wczytaj_dystrybutora)
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
