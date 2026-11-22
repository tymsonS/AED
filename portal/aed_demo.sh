#!/usr/bin/env bash
# AEDane: demo wykazu zbiorczego AED na lokalnym portalu jedną komendą.
#
# Użycie (z dowolnego katalogu):
#   portal/aed_demo.sh             # pobiera świeże dane; bez sieci użyje danych pobranych wcześniej
#   portal/aed_demo.sh --pobierz   # tylko pobiera dane 3 gmin (np. przy dobrym łączu, przed pokazem)
#   portal/aed_demo.sh --offline   # bez internetu – tylko dane pobrane wcześniej
#
# Warunek dla demo (bez --pobierz): portal działa (README-DOCKER-AED.md, kroki 1–6),
# w tym kontenery mcod-admin i mcod-celery. Sam portal działa lokalnie i do demo nie potrzebuje sieci.
#
# 1. Pobiera dane 3 gmin, które publikują dane o AED na dane.gov.pl (Krosno, Przemyśl, Marki),
#    do ingest/data/raw/ – chyba że --offline.
# 2. Buduje z nich pakiety dostawcy (ingest/) – prawdziwe dane, bez ręcznych poprawek.
# 3. Kopiuje aed.csv do portal/media/aed-demo/ (katalog montowany w mcod-admin).
# 4. W kontenerze panelu: zasoby z flagą „Zawiera wykaz defibrylatorów AED”, walidacja portalu
#    i zadanie wykazu zbiorczego (aed_demo_wykaz.py). Wynik: 50 AED w jednym zasobie CSV.
set -euo pipefail

PORTAL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$PORTAL_DIR")"
DEMO_DIR="$PORTAL_DIR/media/aed-demo"
PYTHON="${PYTHON:-python3}"

MODE="online"
case "${1:-}" in
  "") ;;
  --pobierz) MODE="download" ;;
  --offline) MODE="offline" ;;
  -h|--help) sed -n '2,10p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
  *) echo "Nieznana opcja: $1 (dozwolone: --pobierz, --offline)" >&2; exit 2 ;;
esac

# źródło | TERYT gminy | gmina | dostawca | plik w media/aed-demo
PROVIDERS=(
  "danegovpl-krosno|1861011|Krosno|Urząd Miasta Krosna|krosno.csv"
  "danegovpl-przemysl|1862011|Przemyśl|Urząd Miejski w Przemyślu|przemysl.csv"
  "danegovpl-marki|1434021|Marki|Urząd Miasta Marki|marki.csv"
)

has_local_data() {
  compgen -G "$REPO_DIR/ingest/data/raw/$1/resource-*" >/dev/null
}

cd "$REPO_DIR"

# 1. Dane źródłowe: pobranie albo dane pobrane wcześniej.
for entry in "${PROVIDERS[@]}"; do
  IFS='|' read -r source _ municipality _ _ <<<"$entry"
  if [[ "$MODE" == "offline" ]]; then
    has_local_data "$source" || {
      echo "Brak pobranych danych dla $municipality ($source). Uruchom raz z internetem: portal/aed_demo.sh --pobierz" >&2
      exit 1
    }
    echo "$municipality: dane pobrane wcześniej (tryb offline)"
  elif out=$("$PYTHON" -m ingest fetch "$source" 2>&1); then
    echo "$out" | tail -n 1
  elif [[ "$MODE" == "download" ]]; then
    echo "$out" | tail -n 1 >&2
    echo "Nie udało się pobrać danych dla $municipality$(has_local_data "$source" && echo ' – zostają dane pobrane wcześniej')." >&2
    download_failed=1
  else
    has_local_data "$source" || {
      echo "$out" | tail -n 1 >&2
      echo "Nie udało się pobrać danych dla $municipality, a nie ma ich też lokalnie – sprawdź internet." >&2
      exit 1
    }
    echo "UWAGA: $municipality – pobranie się nie udało, używam danych pobranych wcześniej." >&2
  fi
done

if [[ "$MODE" == "download" ]]; then
  if [[ -n "${download_failed:-}" ]]; then
    echo "Nie wszystkie dane udało się pobrać – sprawdź internet i uruchom ponownie." >&2
    exit 1
  fi
  echo "Dane pobrane do ingest/data/raw/. Demo bez internetu: portal/aed_demo.sh --offline"
  exit 0
fi

docker ps --format '{{.Names}}' | grep -qx mcod-admin || {
  echo "Kontener mcod-admin nie działa – najpierw uruchom portal (README-DOCKER-AED.md)." >&2
  exit 1
}

# 2–3. Pakiety dostawcy (bez sieci) i pliki dla portalu.
mkdir -p "$DEMO_DIR"
for entry in "${PROVIDERS[@]}"; do
  IFS='|' read -r source teryt municipality provider file <<<"$entry"
  echo "== $municipality"
  "$PYTHON" -m ingest package "$source" --teryt "$teryt" --gmina "$municipality" --dostawca "$provider" \
    --base-url "https://mcod.local/media/aed-demo/" | grep -E "Walidacja|Błąd" || true
  cp "ingest/data/pakiety/aed-$teryt/aed.csv" "$DEMO_DIR/$file"
done

# 4. Portal. Dużo loguje (sygnały, Elasticsearch) – pokazujemy tylko komunikaty demo i błędy.
echo "== Portal: zasoby z flagą AED, walidacja i wykaz zbiorczy"
docker exec -i mcod-admin python manage.py shell < "$PORTAL_DIR/aed_demo_wykaz.py" 2>&1 \
  | grep -vE "^\[|^NoneType|Overriding existing registry|warnings\.warn| (DEBUG|INFO|WARNING) "

# Usunięte zbiory z poprzedniego uruchomienia zostają w indeksie wyszukiwarki – odświeżamy go.
echo "== Wyszukiwarka portalu: odświeżenie indeksu zbiorów i zasobów"
docker exec mcod-admin python manage.py search_index --rebuild -f --models datasets.Dataset resources.Resource >/dev/null 2>&1

echo "Gotowe. Panel: https://admin.mcod.local (Zbiory danych), API: https://api.mcod.local/1.4/datasets?q=defibrylator"
