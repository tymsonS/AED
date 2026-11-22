#!/usr/bin/env bash
# AEDane: dogrywa artefakty pominięte w repo (#57) z oryginalnego archiwum portalu dane.gov.pl:
#   statics/                   – zbudowany frontend (ok. 80 MB), montowany przez nginx i mcod-local-api,
#   docker/rdfdb/fuseki/dist/  – paczka Apache Jena Fuseki (ok. 50 MB), potrzebna do zbudowania mcod-rdfdb.
# Bez nich `docker compose build` / `up` się nie powiedzie.
#
# Użycie (z dowolnego katalogu):
#   portal/aed_fetch_artifacts.sh                 # pobiera archiwum z dane.gov.pl
#   portal/aed_fetch_artifacts.sh backend.zip     # używa już pobranego archiwum
#
# Archiwum jest sprawdzane sumą SHA-256 wersji, z której pochodzi kod w repo (2.63.0, #57).
# Jeśli dane.gov.pl opublikuje nowszą wersję, skrypt się zatrzyma – wtedy trzeba uzgodnić
# aktualizację kodu portalu z właścicielem obszaru portal/ (AGENTS.md).
set -euo pipefail

ARCHIVE_URL="https://dane.gov.pl/source-code/backend_latest.zip"
EXPECTED_SHA256="85949002eaa9f96c4dc2207c9a62caa29e5eae55d5ea5e9bd78a179ce0c3f47a"
PORTAL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

for tool in curl unzip sha256sum; do
  command -v "$tool" >/dev/null || { echo "Brak programu: $tool" >&2; exit 1; }
done

if [[ $# -ge 1 ]]; then
  archive="$(realpath "$1")"
else
  tmp_dir="$(mktemp -d)"
  trap 'rm -rf "$tmp_dir"' EXIT
  archive="$tmp_dir/backend_latest.zip"
  echo "Pobieram $ARCHIVE_URL (ok. 90 MB)…"
  curl -fSL --progress-bar -o "$archive" "$ARCHIVE_URL"
fi

actual="$(sha256sum "$archive" | cut -d' ' -f1)"
if [[ "$actual" != "$EXPECTED_SHA256" ]]; then
  echo "Suma SHA-256 archiwum się nie zgadza." >&2
  echo "  oczekiwana: $EXPECTED_SHA256 (wersja 2.63.0 z repo)" >&2
  echo "  otrzymana:  $actual" >&2
  echo "Archiwum na dane.gov.pl mogło zostać zaktualizowane – nie dogrywam plików z innej wersji." >&2
  exit 1
fi

echo "Suma SHA-256 zgodna. Rozpakowuję do $PORTAL_DIR …"
unzip -q -o "$archive" 'statics/*' 'docker/rdfdb/fuseki/dist/*' -d "$PORTAL_DIR"

echo "Gotowe:"
du -sh "$PORTAL_DIR/statics" "$PORTAL_DIR/docker/rdfdb/fuseki/dist"
echo "Oba katalogi są w portal/.gitignore – nie trafią do commita."
