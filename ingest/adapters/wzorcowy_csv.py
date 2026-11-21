"""Plik przygotowany przez dostawcę we wzorcowym zakresie danych (python -m ingest package --plik).

Źródło lokalne, jak „dystrybutor”: nic nie pobieramy. Wpis w sources.toml (plik-dostawcy) istnieje
po to, żeby rekordy z pustym zrodlo dostawały identyfikator ze spisu źródeł (AGENTS.md).
Pliki położone w raw/plik-dostawcy/resource-<nazwa>.csv adapter czyta tak samo jak
package --plik (package.read_records_csv): CSV z Excela, puste zrodlo, id_zrodlowe i id_aed
uzupełnione (review #39). Kod gminy nadaje build z granic PRG, jak dla innych źródeł.
"""

from __future__ import annotations

import csv
from pathlib import Path

from ..fields import field_names
from .base import Adapter


class WzorcowyCsvAdapter(Adapter):
    def fetch(self) -> Path:
        raise RuntimeError(f"{self.id}: źródło lokalne – plik dostawcy podaje się w python -m ingest package --plik")

    def records(self, path: Path) -> list[dict]:
        # Ta sama ścieżka co package --plik – jedno miejsce z regułami pliku dostawcy.
        from ..package import read_records_csv

        return read_records_csv(path, default_source=self.id)

    def parse(self, path: Path) -> list[dict]:
        with path.open(encoding="utf-8-sig", newline="") as fh:
            return list(csv.DictReader(fh))

    def map_record(self, raw: dict) -> dict:
        rec = {k: raw.get(k, "") or "" for k in field_names()}
        rec["_uwagi"] = []
        return rec
