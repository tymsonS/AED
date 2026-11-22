"""Czytanie CSV zapisanych w Excelu (lista dystrybutora, plik gminy do pakietu dostawcy).

Polski Excel zapisuje CSV zwykle w Windows-1250 ze średnikiem, a daty jako DD.MM.RRRR
i liczby z przecinkiem dziesiętnym. Tu jest jedna obsługa tych wariantów dla całego ingest/.
"""

from __future__ import annotations

import csv
import io
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


def read_rows(path: Path) -> list[dict]:
    """Wiersze CSV: UTF-8 (z BOM lub bez) albo Windows-1250, separator przecinek albo średnik.
    Wartości przycięte, puste komórki jako „”."""
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1250")
    header = text.split("\n", 1)[0]
    delimiter = ";" if header.count(";") > header.count(",") else ","
    return [{k.strip(): (v or "").strip() for k, v in r.items() if k}
            for r in csv.DictReader(io.StringIO(text), delimiter=delimiter)]


def parse_date(text: str) -> date | None:
    """RRRR-MM-DD albo DD.MM.RRRR / DD.MM.RR (tak zapisuje polski Excel)."""
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d.%m.%y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    return None


# Excel zamienia kody na liczby i gubi zera z przodu (review #39): długość z wzorca schematu.
_ZERO_PAD = {"kod_teryt_gminy": (7,), "dysponent_regon": (9, 14), "dysponent_nip": (10,)}


def _last_sunday(year: int, month: int) -> date:
    day = date(year, month + 1, 1) - timedelta(days=1)
    return day - timedelta(days=(day.weekday() - 6) % 7)


def to_warsaw(moment: datetime) -> datetime:
    """Chwila ze strefą -> czas polski bez strefy (CET/CEST), bez bazy stref.

    Portal dane.gov.pl przyjmuje w danych tabelarycznych tylko daty bez strefy (DATE_BASE_FORMATS
    w portal/mcod/settings/base.py), więc data_aktualizacji to czas polski bez strefy (decyzja
    zespołu w #61). Czas letni w UE: od ostatniej niedzieli marca do ostatniej niedzieli
    października, zmiana o 01:00 UTC.
    """
    utc = moment.astimezone(timezone.utc).replace(tzinfo=None)
    start = datetime.combine(_last_sunday(utc.year, 3), datetime.min.time()).replace(hour=1)
    end = datetime.combine(_last_sunday(utc.year, 10), datetime.min.time()).replace(hour=1)
    return utc + timedelta(hours=2 if start <= utc < end else 1)


def warsaw_now(now: datetime | None = None) -> str:
    """Bieżąca chwila jako czas polski bez strefy, np. 2026-11-21T13:00:00 (pole data_aktualizacji)."""
    return to_warsaw(now or datetime.now(timezone.utc)).isoformat(timespec="seconds")


_ISO_NO_SECONDS = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}")


def parse_datetime(text: str) -> datetime | None:
    """Data z godziną z Excela -> czas polski bez strefy.

    „21.11.2026 12:00” albo „2026-11-21 12:00(:00)” to już czas polski, niezależnie od strefy
    komputera (review #39). Zapis ISO 8601 ze strefą (np. „2026-11-21T12:00:00Z” ze starszych
    plików) przeliczamy na czas polski, bo portal nie przyjmuje daty ze strefą (#61), a zapis
    bez sekund („2026-11-21T13:00”) dostaje „:00”. Poprawny zapis bez strefy -> None (bez zmian).
    """
    for fmt in ("%d.%m.%Y %H:%M", "%d.%m.%Y %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    if "T" in text:
        try:
            moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
        if moment.tzinfo is not None:
            return to_warsaw(moment)
        if _ISO_NO_SECONDS.fullmatch(text):
            return moment
    return None


def polish_datetime(value: str) -> str:
    """Wartość pola datetime na zapis schematu (czas polski bez strefy, z sekundami);
    zapis, którego nie da się rozpoznać albo już poprawny, zostaje bez zmian."""
    stamp = parse_datetime(value) if value else None
    return stamp.isoformat(timespec="seconds") if stamp is not None else value


def excel_values(rec: dict, fields: list[dict]) -> dict:
    """Wartości po Excelu na zapis schematu:
    - daty DD.MM.RRRR -> RRRR-MM-DD, data z godziną -> ISO 8601 z sekundami w czasie polskim, bez strefy,
    - „49,75” -> „49.75”,
    - zera z przodu w TERYT (7 cyfr), REGON (9 lub 14), NIP (10),
    - telefon bez „+”: „48226…” -> „+48226…”.
    Wartość, której nie da się rozpoznać, zostaje bez zmian – opisze ją walidator."""
    out = dict(rec)
    for f in fields:
        name, value = f["name"], out.get(f["name"], "")
        if not value:
            continue
        if f["type"] == "date" and (parsed := parse_date(value)) is not None:
            out[name] = parsed.isoformat()
        elif f["type"] == "datetime" and (stamp := parse_datetime(value)) is not None:
            out[name] = stamp.isoformat(timespec="seconds")  # to samo co polish_datetime
        elif f["type"] == "number" and value.count(",") == 1 and "." not in value:
            out[name] = value.replace(",", ".")
        elif name in _ZERO_PAD and value.isdigit():
            target = next((n for n in _ZERO_PAD[name] if len(value) < n), None)
            if target is not None and len(value) >= target - 2:  # najwyżej 2 zgubione zera
                out[name] = value.zfill(target)
        elif name == "telefon_kontaktowy" and value.isdigit() and value.startswith("48") and len(value) == 11:
            out[name] = "+" + value
    return out
