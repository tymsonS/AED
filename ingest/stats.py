"""Statystyki do prezentacji: ile AED mamy, jak pokrywają Polskę i jakiej są jakości.

Liczymy urządzenia, nie wpisy: punkt OSM, który jest tym samym AED co zweryfikowany
(gaps.verification(), ten_sam_co), nie liczy się drugi raz. Reguły weryfikacji są
te same co w mapie luk, aed-app.geojson i liście dla dystrybutora.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone

from .gaps import STATUS_BRAK, STATUS_PUBLIKUJE


def _pct(n: int, total: int) -> float:
    return round(100 * n / total, 1) if total else 0.0


def _known(value: str, unknown: str) -> bool:
    return bool(value) and value != unknown


# Miary jakości: nazwa -> warunek na rekordzie. Kolejność = kolejność w tabeli.
def _quality_checks(fresh_from: str) -> dict:
    return {
        "ze wskazanym dysponentem": lambda r: bool(r.get("dysponent_nazwa")),
        "z datą weryfikacji": lambda r: bool(r.get("data_weryfikacji")),
        "sprawdzone w ostatnich 12 mies.": lambda r: r.get("data_weryfikacji", "") >= fresh_from,
        "z rodzajem dostępu": lambda r: _known(r.get("dostep", ""), "nieznany"),
        "z godzinami dostępności": lambda r: _known(r.get("godziny_dostepnosci", ""), "nieznane"),
        "publicznie dostępne 24/7": lambda r: r.get("dostep") == "publiczny" and r.get("dostepny_24h") == "tak",
        "z opisem lokalizacji": lambda r: bool(r.get("opis_lokalizacji")),
        "z adresem (miejscowość)": lambda r: bool(r.get("miejscowosc")),
    }


def compute(records: list[dict], statuses: list[dict], sources: list[dict],
            gap_rows: list[dict] | None = None, report: dict | None = None,
            today: date | None = None) -> dict:
    today = today or date.today()
    fresh_from = (today - timedelta(days=365)).isoformat()
    pairs = list(zip(records, statuses, strict=True))
    devices = [(r, s) for r, s in pairs if not s["ten_sam_co"]]
    verified = [r for r, s in devices if s["zweryfikowany"]]
    unverified = [r for r, s in devices if not s["zweryfikowany"]]

    by_source = Counter(r["zrodlo"] for r in records)
    names = {s["id"]: s for s in sources}
    checks = _quality_checks(fresh_from)

    def quality(recs: list[dict]) -> dict:
        return {name: {"aed": sum(1 for r in recs if f(r)), "procent": _pct(sum(1 for r in recs if f(r)), len(recs))}
                for name, f in checks.items()}

    out = {
        "data": today.isoformat(),
        "wygenerowano": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "wpisy": len(records),
        "aed": len(devices),
        "aed_zweryfikowane": len(verified),
        "aed_niezweryfikowane": len(unverified),
        "duplikaty_osm_pominiete": len(pairs) - len(devices),
        "poza_obszarem_dysponenta": sum(s["poza_obszarem_dysponenta"] for s in statuses),
        "zrodla": [
            {"id": sid, "dysponent": names.get(sid, {}).get("dysponent", ""),
             "poziom_zaufania": names.get(sid, {}).get("poziom_zaufania", 3), "wpisy": n}
            for sid, n in sorted(by_source.items(), key=lambda kv: -kv[1])
        ],
        "jakosc": {
            "wszystkie": quality([r for r, _ in devices]),
            "zweryfikowane": quality(verified),
            "niezweryfikowane": quality(unverified),
        },
    }
    if gap_rows:
        out["pokrycie"] = _coverage(gap_rows, devices)
    if report:
        out["walidacja"] = {
            "rekordy": report["rekordy"],
            "rekordy_z_bledami": report["rekordy_z_bledami"],
            "procent_z_bledami": _pct(report["rekordy_z_bledami"], report["rekordy"]),
            "bledy": report["bledy"],
            "ostrzezenia": report["ostrzezenia"],
            "najczestsze_problemy": dict(list(report["problemy_wg_pola"].items())[:6]),
        }
    return out


def _coverage(gap_rows: list[dict], devices: list[tuple[dict, dict]]) -> dict:
    with_owner: dict[str, int] = defaultdict(int)
    for r, _ in devices:
        if r.get("dysponent_nazwa") and r.get("wojewodztwo"):
            with_owner[r["wojewodztwo"]] += 1
    woj: dict[str, Counter] = defaultdict(Counter)
    for g in gap_rows:
        w = woj[g["wojewodztwo"]]
        w["gminy"] += 1
        w["gminy_z_aed"] += g["status"] != STATUS_BRAK
        w["gminy_publikujace"] += g["status"] == STATUS_PUBLIKUJE
        w["aed"] += g["aed_lacznie"]
        w["aed_zweryfikowane"] += g["aed_zweryfikowane"]
        w["km2"] += float(g["powierzchnia_km2"] or 0)
    rows = []
    for name, w in sorted(woj.items(), key=lambda kv: -kv[1]["aed"]):
        rows.append({
            "wojewodztwo": name,
            "aed": w["aed"],
            "aed_zweryfikowane": w["aed_zweryfikowane"],
            "aed_z_dysponentem_procent": _pct(with_owner[name], w["aed"]),
            "gminy": w["gminy"],
            "gminy_bez_aed": w["gminy"] - w["gminy_z_aed"],
            "gminy_z_aed_procent": _pct(w["gminy_z_aed"], w["gminy"]),
            "gminy_publikujace": w["gminy_publikujace"],
            "aed_na_100_km2": round(100 * w["aed"] / w["km2"], 2) if w["km2"] else 0,
        })
    total = len(gap_rows)
    z_aed = sum(g["status"] != STATUS_BRAK for g in gap_rows)
    return {
        "gminy": total,
        "gminy_z_aed": z_aed,
        "gminy_z_aed_procent": _pct(z_aed, total),
        "gminy_publikujace": sum(g["status"] == STATUS_PUBLIKUJE for g in gap_rows),
        "gminy_z_aed_bez_zadnego_dysponenta": sum(
            g["aed_lacznie"] > 0 and g["aed_zweryfikowane"] == 0 and g["niezweryfikowane_z_dysponentem"] == 0
            for g in gap_rows),
        "wojewodztwa": rows,
    }


def _n(x: int | float) -> str:
    """Liczba po polsku: spacja tysięcy, przecinek dziesiętny."""
    if isinstance(x, float):
        return f"{x:,.1f}".replace(",", " ").replace(".", ",")
    return f"{x:,}".replace(",", " ")


def render_md(s: dict) -> str:
    lines = [
        f"# Misja AED – statystyki ({s['data']})",
        "",
        "Wygenerowane przez `python -m ingest stats`. Liczymy urządzenia, nie wpisy: punkt OSM, "
        "który jest tym samym AED co zweryfikowany, liczy się raz.",
        "",
        "## Najważniejsze liczby",
        "",
        f"- **{_n(s['aed'])} AED** w danych (wpisy: {_n(s['wpisy'])}, pominięte duplikaty OSM: "
        f"{_n(s['duplikaty_osm_pominiete'])}).",
        f"- **{_n(s['aed_zweryfikowane'])} zweryfikowanych** przez instytucje "
        f"({_n(_pct(s['aed_zweryfikowane'], s['aed']))}%), {_n(s['aed_niezweryfikowane'])} niezweryfikowanych.",
    ]
    q = s["jakosc"]["niezweryfikowane"]
    lines.append(f"- Wśród niezweryfikowanych: {_n(q['ze wskazanym dysponentem']['procent'])}% ma dysponenta, "
                 f"{_n(q['sprawdzone w ostatnich 12 mies.']['procent'])}% sprawdzono w ostatnim roku.")
    if "pokrycie" in s:
        p = s["pokrycie"]
        lines += [
            f"- AED w danych ma **{_n(p['gminy_z_aed'])} z {_n(p['gminy'])} gmin** ({_n(p['gminy_z_aed_procent'])}%); "
            f"dane na dane.gov.pl publikują {_n(p['gminy_publikujace'])}.",
            f"- W {_n(p['gminy_z_aed_bez_zadnego_dysponenta'])} gminach są AED, ale przy żadnym nie ma dysponenta.",
        ]
    lines += ["", "## Źródła", "", "| Źródło | Dysponent | Poziom zaufania | Wpisy |", "|---|---|---|---:|"]
    lines += [f"| `{z['id']}` | {z['dysponent']} | {z['poziom_zaufania']} | {_n(z['wpisy'])} |" for z in s["zrodla"]]
    lines += ["", "## Jakość danych", "",
              "| Miara | Wszystkie | Zweryfikowane | Niezweryfikowane |", "|---|---:|---:|---:|"]
    for name in s["jakosc"]["wszystkie"]:
        cells = [f"{_n(s['jakosc'][g][name]['procent'])}%" for g in ("wszystkie", "zweryfikowane", "niezweryfikowane")]
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    if "pokrycie" in s:
        lines += ["", "## Pokrycie województw", "",
                  "| Województwo | AED | Zweryfikowane | Z dysponentem | Gminy bez AED | Gminy z AED | AED / 100 km² |",
                  "|---|---:|---:|---:|---:|---:|---:|"]
        for w in s["pokrycie"]["wojewodztwa"]:
            lines.append(
                f"| {w['wojewodztwo']} | {_n(w['aed'])} | {_n(w['aed_zweryfikowane'])} | "
                f"{_n(w['aed_z_dysponentem_procent'])}% | {_n(w['gminy_bez_aed'])} z {_n(w['gminy'])} | "
                f"{_n(w['gminy_z_aed_procent'])}% | {_n(float(w['aed_na_100_km2']))} |")
    if "walidacja" in s:
        v = s["walidacja"]
        lines += ["", "## Walidacja względem wzorcowego zakresu danych", "",
                  f"{_n(v['rekordy_z_bledami'])} z {_n(v['rekordy'])} wpisów ({_n(v['procent_z_bledami'])}%) ma błędy; "
                  f"{_n(v['bledy'])} błędów, {_n(v['ostrzezenia'])} ostrzeżeń. Najczęstsze problemy:", "",
                  "| Pole | Problemy |", "|---|---:|"]
        lines += [f"| `{k}` | {_n(n)} |" for k, n in v["najczestsze_problemy"].items()]
    lines += ["", "„Brak AED w danych” nie znaczy, że w gminie nie ma AED – nikt ich nie zgłosił. "
              "Dane OSM: © współtwórcy OpenStreetMap, ODbL.", ""]
    return "\n".join(lines)
