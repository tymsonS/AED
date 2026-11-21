"""AED potwierdzone przez dystrybutora (wynik python -m ingest wczytaj-dystrybutora).

Plik potwierdzone.csv jest już we wzorcowym zakresie danych, więc adapter tylko go czyta.
Źródło jest lokalne: nic nie pobieramy, pliki kopiuje do raw/<id>/ polecenie
wczytaj-dystrybutora (resource-<obszar>.csv i usuniete-<obszar>.csv).
"""

from __future__ import annotations

import csv
from pathlib import Path

from ..fields import field_names
from .base import Adapter


class DystrybutorAdapter(Adapter):
    def fetch(self) -> Path:
        raise RuntimeError(
            f"{self.id}: źródło lokalne – dane dodaje python -m ingest wczytaj-dystrybutora <plik> --zrodlo {self.id}"
        )

    def parse(self, path: Path) -> list[dict]:
        with path.open(encoding="utf-8", newline="") as fh:
            return list(csv.DictReader(fh))

    def map_record(self, raw: dict) -> dict:
        rec = {k: raw.get(k, "") or "" for k in field_names()}
        rec["_uwagi"] = []
        return rec

    def missing_reports(self) -> dict[str, dict]:
        """id_aed -> {opis: „kto, kiedy”, poinformowano: data powiadomienia dysponenta albo „”}
        dla AED, których dystrybutor nie znalazł na miejscu (brak_urzadzenia)."""
        reports: dict[str, dict] = {}
        for path in sorted(self.raw_dir.glob("usuniete-*.csv")):
            with path.open(encoding="utf-8", newline="") as fh:
                for r in csv.DictReader(fh):
                    if not r.get("id_aed"):
                        continue
                    previous = reports.get(r["id_aed"], {}).get("poinformowano", "")
                    informed = r.get("poinformowano_dysponenta", "") or ""
                    reports[r["id_aed"]] = {
                        "opis": f"{r.get('zglosil', '') or 'dystrybutor'}, {r.get('data_sprawdzenia', '')}",
                        # Review #42: pusta data z kolejnego pliku nie kasuje wcześniejszej – bierzemy najnowszą.
                        "poinformowano": max(previous, informed),
                    }
        return reports
