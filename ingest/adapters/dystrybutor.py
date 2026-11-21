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
        best: dict[str, tuple] = {}
        for path in sorted(self.raw_dir.glob("usuniete-*.csv")):
            with path.open(encoding="utf-8", newline="") as fh:
                for r in csv.DictReader(fh):
                    if not r.get("id_aed"):
                        continue
                    informed = r.get("poinformowano_dysponenta", "") or ""
                    # Jedno zgłoszenie na AED, a opis i data z tego samego wiersza (review #42):
                    # wygrywa zgłoszenie z najnowszą datą powiadomienia, a bez niej – najnowsze sprawdzenie.
                    # Pusta data z kolejnego pliku nie kasuje więc wcześniejszej.
                    rank = (bool(informed), informed, r.get("data_sprawdzenia", ""))
                    if r["id_aed"] not in best or rank >= best[r["id_aed"]][0]:
                        best[r["id_aed"]] = (rank, {
                            "opis": f"{r.get('zglosil', '') or 'dystrybutor'}, {r.get('data_sprawdzenia', '')}",
                            "poinformowano": informed,
                        })
        return {id_aed: report for id_aed, (_, report) in best.items()}
