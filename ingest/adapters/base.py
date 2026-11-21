"""Bazowy adapter źródła danych."""

from __future__ import annotations

import json
import urllib.request
from abc import ABC, abstractmethod
from pathlib import Path

USER_AGENT = "misja-aed-ingest/0.1 (HackNation 2026)"


class Adapter(ABC):
    """Jedno źródło = jedna instancja. Kolejność: fetch() -> parse() -> map_record()."""

    def __init__(self, source: dict, raw_dir: Path):
        self.source = source
        self.id: str = source["id"]
        self.raw_dir = raw_dir / self.id

    @abstractmethod
    def fetch(self) -> Path:
        """Pobiera surowe dane do raw_dir (bez modyfikacji) i zwraca ścieżkę pliku."""

    @abstractmethod
    def parse(self, path: Path) -> list[dict]:
        """Czyta surowy plik i zwraca rekordy w układzie źródła."""

    @abstractmethod
    def map_record(self, raw: dict) -> dict:
        """Mapuje jeden rekord źródła na pola wzorcowego zakresu danych."""

    def records(self, path: Path) -> list[dict]:
        return [self.map_record(r) for r in self.parse(path)]


def http_get(url: str, accept: str = "*/*", timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def http_get_json(url: str) -> dict:
    return json.loads(http_get(url, accept="application/json"))
