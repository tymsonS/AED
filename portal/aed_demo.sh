#!/usr/bin/env bash
# AEDane: demo wykazu zbiorczego AED na lokalnym portalu jedną komendą.
#
# Warunek: portal działa (README-DOCKER-AED.md, kroki 1–6), w tym kontenery mcod-admin i mcod-celery.
# Użycie (z dowolnego katalogu):
#   portal/aed_demo.sh
#
# 1. Buduje pakiety dostawcy z ingest/ dla 3 gmin, które publikują dane o AED na dane.gov.pl
#    (Krosno, Przemyśl, Marki) – prawdziwe dane, bez żadnych ręcznych poprawek.
# 2. Kopiuje aed.csv do portal/media/aed-demo/ (katalog montowany w mcod-admin).
# 3. W kontenerze panelu: zasoby z flagą „Zawiera wykaz defibrylatorów AED”, walidacja portalu
#    i zadanie wykazu zbiorczego (aed_demo_wykaz.py). Wynik: 50 AED w jednym zasobie CSV.
set -euo pipefail

PORTAL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$PORTAL_DIR")"
DEMO_DIR="$PORTAL_DIR/media/aed-demo"
PYTHON="${PYTHON:-python3}"

# źródło | TERYT gminy | gmina | dostawca | plik w media/aed-demo
PROVIDERS=(
  "danegovpl-krosno|1861011|Krosno|Urząd Miasta Krosna|krosno.csv"
  "danegovpl-przemysl|1862011|Przemyśl|Urząd Miejski w Przemyślu|przemysl.csv"
  "danegovpl-marki|1434021|Marki|Urząd Miasta Marki|marki.csv"
)

docker ps --format '{{.Names}}' | grep -qx mcod-admin || {
  echo "Kontener mcod-admin nie działa – najpierw uruchom portal (README-DOCKER-AED.md)." >&2
  exit 1
}

mkdir -p "$DEMO_DIR"
cd "$REPO_DIR"
for entry in "${PROVIDERS[@]}"; do
  IFS='|' read -r source teryt municipality provider file <<<"$entry"
  echo "== $municipality"
  "$PYTHON" -m ingest fetch "$source"
  "$PYTHON" -m ingest package "$source" --teryt "$teryt" --gmina "$municipality" --dostawca "$provider" \
    --base-url "https://mcod.local/media/aed-demo/" | grep -E "Walidacja|Błąd" || true
  cp "ingest/data/pakiety/aed-$teryt/aed.csv" "$DEMO_DIR/$file"
done

echo "== Portal: zasoby z flagą AED, walidacja i wykaz zbiorczy"
# Portal dużo loguje (sygnały, Elasticsearch) – pokazujemy tylko komunikaty demo i błędy.
docker exec -i mcod-admin python manage.py shell < "$PORTAL_DIR/aed_demo_wykaz.py" 2>&1 \
  | grep -vE "^\[|^NoneType|Overriding existing registry|warnings\.warn| (DEBUG|INFO|WARNING) "

# Usunięte zbiory z poprzedniego uruchomienia zostają w indeksie wyszukiwarki – odświeżamy go.
echo "== Wyszukiwarka portalu: odświeżenie indeksu zbiorów i zasobów"
docker exec mcod-admin python manage.py search_index --rebuild -f --models datasets.Dataset resources.Resource >/dev/null 2>&1

echo "Gotowe. Panel: https://admin.mcod.local (Zbiory danych), API: https://api.mcod.local/1.4/datasets?q=defibrylator"
