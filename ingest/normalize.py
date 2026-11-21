"""Wspólne czyszczenie danych z różnych źródeł."""

from __future__ import annotations

import re
import uuid

# Prostokąt obejmujący Polskę – ten sam zakres co ograniczenia w schemacie.
LAT_MIN, LAT_MAX = 49.0, 54.9
LON_MIN, LON_MAX = 14.1, 24.2

# Stała przestrzeń nazw: to samo (zrodlo, id_zrodlowe) zawsze daje to samo id_aed.
AED_NAMESPACE = uuid.UUID("6f1c2a3e-8a4b-4c1d-9e2f-0a7b5c3d1e00")

_POSTCODE_CITY = re.compile(r"(?P<kod>\d{2}-\d{3})\s+(?P<miasto>.+)$")
_STREET_NUMBER = re.compile(r"^(?P<ulica>.*?)\s+(?P<numer>\d+[A-Za-z]?(?:/\d+[A-Za-z]?)?)$")
_STREET_PREFIX = re.compile(r"^(ul|al|os|pl)\.+\s*", re.IGNORECASE)


def stable_id(zrodlo: str, id_zrodlowe: str) -> str:
    return str(uuid.uuid5(AED_NAMESPACE, f"{zrodlo}:{id_zrodlowe}"))


def in_poland(lat: float, lon: float) -> bool:
    return LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX


def fix_coordinates(lat: float, lon: float) -> tuple[float, float, bool]:
    """Zwraca (lat, lon, zamienione). Wykrywa zamienioną kolejność współrzędnych.

    Przykład z dane.gov.pl: Marki ma w nagłówku „długość, szerokość”,
    a w wierszach odwrotnie.
    """
    if in_poland(lat, lon):
        return lat, lon, False
    if in_poland(lon, lat):
        return lon, lat, True
    return lat, lon, False


def parse_address(text: str) -> dict[str, str]:
    """Rozbija adres typu „ul. Okólna 14, 05-270 Marki” na pola schematu."""
    out = {"ulica": "", "numer_budynku": "", "kod_pocztowy": "", "miejscowosc": ""}
    text = " ".join(text.split())
    # Puste człony, np. „ul. Kazimierza Wielkiego 4, , 38-400 Krosno” (Krosno, dane.gov.pl).
    text = ", ".join(part.strip() for part in text.split(",") if part.strip())
    if not text:
        return out
    street_part, _, rest = text.rpartition(",")
    if not street_part:
        street_part, rest = text, ""
    m = _POSTCODE_CITY.search(rest.strip())
    if m:
        out["kod_pocztowy"] = m["kod"]
        out["miejscowosc"] = m["miasto"].strip()
    street = _STREET_PREFIX.sub("", street_part.strip())
    m = _STREET_NUMBER.match(street)
    if m:
        out["ulica"], out["numer_budynku"] = m["ulica"].strip(), m["numer"]
    else:
        out["ulica"] = street
    return out


def normalize_phone(text: str) -> str:
    """Numer do E.164 (+48…). Pusty, jeśli nie da się go jednoznacznie odczytać."""
    digits = re.sub(r"[^\d+]", "", text or "")
    if digits.startswith("00"):
        digits = "+" + digits[2:]
    if digits.startswith("+"):
        return digits if re.fullmatch(r"\+[1-9]\d{6,14}", digits) else ""
    if len(digits) == 9:
        return "+48" + digits
    return ""


def clean_text(text: str) -> str:
    return " ".join((text or "").split())
