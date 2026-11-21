# Misja AED – plan techniczny: schemat danych i skrypty zbierające

> Stan na 21.11.2026. Bieżące notatki i komentarze: [wersja robocza w Claude Docs](https://claude.ai/artifact/NKU5PW64Vx88gpswwQjN5g). Ten plik to wersja, na której się opieramy – poprawki wprowadzamy przez PR. Zasady pracy: [AGENTS.md](../AGENTS.md).

Budujemy jeden otwarty zbiór AED: adaptery pobierają dane z rozproszonych źródeł, pipeline je normalizuje, scala i waliduje względem wzorcowego schematu, a wynik publikujemy jako CSV/JSON/GeoJSON + XLSX zgodnie z zasadami dane.gov.pl. Kryterium „zgodność z dane.gov.pl” waży 30%, a „wzorcowy zakres danych” 10% – schemat i walidator są więc rdzeniem prototypu.

## Architektura

Pipeline jest liniowy i idempotentny: każdy etap czyta wynik poprzedniego z dysku, więc można go uruchamiać i debugować osobno.

1. **Fetch** – adapter per źródło pobiera surowe dane do `data/raw/<source>/<data>.{json,csv,xlsx}` (bez modyfikacji, z zapisaną datą pobrania i URL-em).
2. **Map** – adapter mapuje rekordy źródła na wspólny model `AedRecord` (pydantic) i zapisuje `data/staged/<source>.parquet`.
3. **Normalize** – wspólne czyszczenie: adresy, telefony, godziny dostępności do składni `opening_hours`, współrzędne do WGS84 (EPSG:4326).
4. **Geocode / enrich** – brakujące współrzędne z adresu, brakujące kody TERYT ze współrzędnych.
5. **Deduplicate & merge** – łączenie tych samych urządzeń z różnych źródeł, z zachowaniem pochodzenia każdego pola.
6. **Validate** – walidacja względem schematu (Frictionless Table Schema + reguły biznesowe); raport błędów per źródło.
7. **Export** – `aed.csv` (UTF-8), `aed.geojson`, `aed.json`, `aed.xlsx` + metadane zbioru; to są zasoby do wgrania na dane.gov.pl.

Ten sam walidator z kroku 6 wystawiamy w prototypie jako narzędzie dla dysponentów: wgrywają swój CSV/XLSX, dostają listę błędów i plik gotowy do publikacji. To bezpośrednio odpowiada na „ułatwienie zbierania danych” z treści zadania.

Interfejs walidatora i mapy (`app/`) spełnia wymagania z treści zadania: WCAG 2.2 AA (kontrast, obsługa klawiaturą, etykiety pól formularza, komunikaty błędów czytelne dla czytników ekranu), responsywność mobile first i język polski. Lista ograniczeń dostępności trafia do prezentacji.

## Źródła danych

Zbiór ma pokrywać **całą Polskę**. Najważniejsze są źródła zweryfikowane – rządowe i samorządowe – i to one wygrywają przy scalaniu. Same jednak nie pokryją kraju, więc luki uzupełniamy źródłami społecznymi, wyraźnie oznaczonymi jako niezweryfikowane. Docelowo luki zamyka kampania: każde miasto i każdy dysponent publikuje w jednym wzorcowym formacie (`schema/`), a nasz walidator mu to ułatwia.

### Poziomy zaufania

| Poziom | Typ źródła | Przykłady | Rola przy scalaniu |
| --- | --- | --- | --- |
| 1 – zweryfikowane | Rejestry i dane administracji publicznej | dane.gov.pl, rejestr AED Państwowego Ratownictwa Medycznego (jeśli dostępny), portale otwartych danych miast i województw | Wygrywa przy konflikcie pól |
| 2 – od dysponenta | Dane przesłane przez właściciela urządzenia | upload przez walidator w `app/` (firmy, uczelnie, szpitale, urzędy) | Wygrywa z poziomem 3 |
| 3 – społeczne | Mapy tworzone przez społeczność | OpenStreetMap (`emergency=defibrillator`) | Uzupełnia pokrycie kraju; rekord oznaczony `metoda_weryfikacji = import` |

Poziom zaufania zapisujemy w `ingest/sources.yaml` razem z id źródła, dysponentem, URL, licencją i częstotliwością odświeżania.

### Co jest dziś na dane.gov.pl (rozpoznanie 21.11.2026)

Wyszukiwanie w API dane.gov.pl („defibrylator”, „defibrylatory”, „AED”) zwraca tylko **4 zbiory z lokalizacjami AED** – wszystkie od urzędów miast, każdy w innym formacie:

| Zbiór (id) | Dysponent | Rekordy | Format i stan | Licencja |
| --- | --- | --- | --- | --- |
| [Lokalizacja defibrylatorów (AED)](https://dane.gov.pl/pl/dataset/39512) (39512) | Urząd m.st. Warszawy | – | Zasób „JSON” prowadzi do strony katalogu Warszawy; dane tylko przez API `dane.um.warszawa.pl` z tokenem użytkownika | CC BY 4.0 |
| [Lokalizacje AED w Przemyślu](https://dane.gov.pl/pl/dataset/4581) (4581) | Urząd Miejski w Przemyślu | 21 | GeoJSON/CSV/JSON/XML; adres rozbity na pola, opis i zdjęcie | CC0 1.0 |
| [Defibrylatory w Mieście Krosno](https://dane.gov.pl/pl/dataset/3624) (3624) | Urząd Miasta Krosna | 21 | CSV: długość, szerokość, nazwa, lokalizacja, adres, id | CC0 1.0 |
| [Defibrylatory na terenie Miasta Marki](https://dane.gov.pl/pl/dataset/4955) (4955) | Urząd Miasta Marki | 8 | CSV/XLSX o tych samych kolumnach co Krosno, ale każdy wiersz w cudzysłowie i **współrzędne zamienione względem nagłówka** | CC BY 4.0 |

Wnioski:
- **Pokrycie:** 4 miasta z ponad 2 400 gmin. To najmocniejszy argument w prezentacji za wzorcowym zakresem danych i kampanią.
- **Brak standardu:** te same informacje w czterech różnych układach, z błędami (zamienione współrzędne, zasób prowadzący do strony WWW). Każdy z tych problemów walidator ma wykrywać.
- **Adaptery:** jeden adapter dane.gov.pl z mapowaniem kolumn per zbiór w `sources.yaml`, plus osobny adapter API Warszawy (token w `.env`).

### Do znalezienia i potwierdzenia

- Portale otwartych danych miast i województw, które mają AED, ale nie opublikowały ich na dane.gov.pl.
- Rejestr AED w systemie Państwowego Ratownictwa Medycznego – zapytać organizatorów.
- Licencja i warunki użycia OSM (ODbL) przy łączeniu z danymi na CC BY / CC0 – patrz „Ryzyka”.

## Wzorcowy schemat danych AED

Źródłem prawdy jest `schema/aed.schema.json` (Frictionless Table Schema, 39 pól) z obszaru `schema/` – wersja v0.1 w PR #9. Ten plan nie powiela listy pól, żeby dwie kopie się nie rozjechały; poniżej tylko zasady i decyzje.

- **Jeden wiersz = jedno urządzenie.** Nazwy kolumn w snake_case po polsku bez znaków diakrytycznych.
- **Trzy poziomy pól:** wymagane (bez nich rekord odrzucamy), zalecane (ostrzeżenie w walidatorze), opcjonalne.
- **Grupy pól:** identyfikacja (`id_aed`, `id_zrodlowe`, `numer_seryjny`), lokalizacja (WGS84, adres, TERYT, `opis_lokalizacji`, `kondygnacja`), dostępność (`dostep`, `godziny_dostepnosci` w składni `opening_hours`, `dostepny_24h`, szafka zamykana), urządzenie, stan i terminy przeglądów, dysponent, weryfikacja, metadane (`zrodlo`, `licencja`, `data_aktualizacji`).
- **Brakujące godziny:** `godziny_dostepnosci` przyjmuje `nieznane`, a `dostepny_24h` wartości `tak` / `nie` / `nieznane` – rekord bez godzin nie jest odrzucany (decyzja Krystiana w #9).
- **`id_aed` (propozycja do decyzji właściciela `schema/`):** nadaje je `ingest/` przy scalaniu, więc w szablonie dla dysponenta pole zostaje puste. Walidator wymaga go dopiero w zbiorze wynikowym, nie w pliku od dysponenta.
- **Bez danych osobowych:** `telefon_kontaktowy` to wyłącznie numer instytucji.
- **Jedno źródło, wiele artefaktów:** ze schematu generujemy wzorcowy XLSX (arkusze „Dane”, „Słownik”, „Przykład”), modele pydantic w `ingest/` i dokumentację. Zmiana nazwy lub typu pola wymaga zgody właścicieli `ingest/` i `app/`.

## Skrypty zbierające

Python 3.12, kod w katalogu `ingest/` (obszar „pobieranie i scalanie danych” z `AGENTS.md`), CLI `aed fetch|map|build|validate|export <source|all>`. Schemat i wzorcowy XLSX leżą w `schema/` – to kontrakt między `ingest/` a `app/`, więc zmiana nazwy lub typu pola wymaga zgody właścicieli obu obszarów. Adapter to klasa z dwiema metodami – dodanie nowego dysponenta to nowy plik albo sam wpis mapowania w YAML.

```
schema/                         # obszar: wzorcowy zakres danych
  aed.schema.json               # źródło prawdy schematu
  wzorcowy-zakres-danych-aed.xlsx
ingest/                         # obszar: pobieranie i scalanie danych
  sources.yaml                  # rejestr źródeł i mapowań kolumn
  models.py                     # AedRecord (pydantic), generowany ze schematu
  adapters/
    base.py                     # class Adapter: fetch() -> raw, map(raw) -> list[AedRecord]
    osm_overpass.py
    danegovpl.py                # generyczny: zasoby CSV/XLSX/JSON + mapowanie z YAML
    city_<nazwa>.py
  normalize.py  geocode.py  dedupe.py  validate.py  export.py
  cli.py
  data/raw/ staged/ out/        # poza gitem, poza out/ z przykładowym wynikiem
  tests/fixtures/               # małe próbki z każdego źródła
```

Sekrety (np. klucze API) tylko w `.env`, który jest w `.gitignore`. Zależności (`requirements.txt`) dodajemy osobnym, małym PR-em, bo to plik wspólny.

- **HTTP:** `httpx` z retry i backoffem, nagłówek User-Agent z nazwą projektu, cache odpowiedzi na dysku, żeby nie odpytywać API przy każdym uruchomieniu.
- **Overpass:** jedno zapytanie `area["ISO3166-1"="PL"]` + `node/way["emergency"="defibrillator"]`, wynik `out center tags`.
- **dane.gov.pl:** wyszukiwanie zbiorów przez API, pobranie zasobów, zapis metadanych (dysponent, licencja, data modyfikacji). Kolumny mapujemy przez `sources.yaml`, np. `Lokalizacja -> opis_lokalizacji`.
- **Dane:** `pandas` lub `polars`, `openpyxl` do XLSX, `pyproj`/`shapely` do geometrii, `rapidfuzz` do porównywania nazw, `frictionless` do walidacji.
- **Testy:** `pytest` na fixture'ach – każdy adapter ma test mapowania na 5–10 rekordach, bez sieci.
- **Odświeżanie:** GitHub Actions z cronem (np. raz na dobę) uruchamia `aed build all` i publikuje `data/out/` jako artefakt – dowodzi „możliwie aktualnego” zbioru.

## Normalizacja, geokodowanie i deduplikacja

To jest miejsce, gdzie integrujemy „informacje od wszystkich dysponentów w jednym zbiorze” – i gdzie łatwo o błędy, więc każda decyzja scalania jest zapisywana.

- **Normalizacja:** trim i unifikacja wielkości liter, kody pocztowe do `NN-NNN`, telefony do E.164, wartości tak/nie z różnych zapisów (`1`, `TAK`, `yes`), godziny z opisów typu „pn–pt 8–16” do `opening_hours`; czego nie da się sparsować, zostaje w `opis_lokalizacji` z flagą.
- **Układy współrzędnych:** wykrywanie EPSG:2180 (PUWG 1992) i przeliczenie do WGS84 przez `pyproj`; odrzucanie punktów poza granicą Polski i zamienionych lat/lon.
- **Geokodowanie:** adres → współrzędne przez usługi GUGiK (punkty adresowe PRG), awaryjnie Nominatim z limitem 1 zapytania/s. Współrzędne → TERYT przez przecięcie z granicami gmin PRG (offline, `geopandas`).
- **Kandydaci na duplikat:** pary rekordów z różnych źródeł w promieniu 50 m (indeks przestrzenny).
- **Ocena pary:** ten sam numer seryjny = duplikat; inaczej wynik z odległości, podobieństwa nazwy obiektu i adresu (`rapidfuzz`). Powyżej progu scalamy, w strefie szarej oznaczamy do ręcznego przeglądu.
- **Scalanie pól:** dla każdego pola wygrywa źródło o wyższym poziomie zaufania (1 – zweryfikowane, 2 – od dysponenta, 3 – społeczne), przy remisie – nowsza `data_weryfikacji`. Pochodzenie każdego pola zapisujemy w tabeli `provenance` (id_aed, pole, źródło, wartość).
- **Stabilne `id_aed`:** UUID nadany raz i przechowywany w mapie `id_zrodlowe → id_aed`, żeby kolejne odświeżenia nie zmieniały identyfikatorów.

## Walidacja i publikacja zgodna z dane.gov.pl

Wynik pipeline'u musi być plikiem, który dysponent może wgrać na dane.gov.pl bez poprawek. Szczegółowe wymagania portalu sprawdzamy w [bazie wiedzy dane.gov.pl](https://dane.gov.pl/pl/knowledgebase/useful-materials) i [kodzie portalu](https://dane.gov.pl/source-code/) – poniższe to plan, nie potwierdzona lista.

- **Formaty:** CSV (UTF-8, przecinek, nagłówek w pierwszym wierszu), JSON, GeoJSON i XLSX. Żadnych PDF/DOC, zgodnie z wymogiem maszynowej czytelności.
- **Walidacja techniczna:** typy, formaty, słowniki wartości, wymagane pola – automatycznie ze schematu Frictionless.
- **Walidacja biznesowa:** współrzędne w Polsce i w gminie z `kod_teryt_gminy`, spójność `dostepny_24h` z `godziny_dostepnosci`, sumy kontrolne REGON/NIP, ostrzeżenie, gdy przegląd jest starszy niż 12 miesięcy albo elektrody lub bateria straciły ważność, duplikaty `id_zrodlowe`. Pełna lista reguł: `schema/README.md`.
- **Raport:** `validation_report.json` + czytelna wersja HTML: liczba błędów i ostrzeżeń per pole i per źródło. Zrzuty z raportu idą do prezentacji jako dowód spełnienia wymagań.
- **Metadane zbioru:** tytuł, opis, dysponent, licencja (proponujemy CC BY 4.0, przy danych z OSM osobny zasób na ODbL), częstotliwość aktualizacji, słowa kluczowe, kategoria. Przygotowujemy je w formacie zgodnym z DCAT-AP PL, jeśli portal to obsługuje dla harwestera.
- **Wzorcowy XLSX:** `schema/wzorcowy-zakres-danych-aed.xlsx` generowany ze schematu (#9) – spełnia wymóg formalny pliku z wzorcowym zakresem danych.

## Podział pracy i kolejność zadań

Schemat v0.1 jest w przeglądzie (#9). Dalej jedno źródło przez cały pipeline, dopiero potem kolejne źródła. Dzięki temu po kilku godzinach mamy działający koniec-do-końca wynik do pokazania.

- [ ] Przejrzeć i scalić schemat v0.1 (#9), rozstrzygnąć `id_aed` w szablonie dysponenta
- [ ] Szkielet `ingest/`: `models.py`, `Adapter` bazowy, CLI
- [ ] Adapter dane.gov.pl + mapowania 3 zbiorów (Przemyśl, Krosno, Marki) + fixture + test
- [ ] Adapter API Warszawy (token w `.env`)
- [ ] Pierwszy pełny przebieg: dane.gov.pl → normalize → validate → export CSV/GeoJSON
- [ ] Wyszukać portale miast i województw z danymi AED poza dane.gov.pl
- [ ] Adapter OSM Overpass jako uzupełnienie pokrycia całej Polski (poziom 3)
- [ ] Geokodowanie i TERYT
- [ ] Deduplikacja i scalanie z `provenance`
- [ ] Walidator jako usługa dla dysponentów (upload CSV/XLSX → raport + poprawiony plik) w `app/`, zgodny z WCAG 2.2 AA i responsywny
- [ ] Raport walidacji i statystyki do prezentacji (liczba AED, pokrycie województw, % z godzinami dostępności)
- [ ] GitHub Actions z cronem odświeżającym zbiór
- [ ] Rejestr AI zgodnie z `AGENTS.md`: wpis w `docs/ai-usage/<imię>.md` na gałęzi, przy scalaniu przeniesiony do `docs/ai-usage.md` (wymóg §2 pkt 8 regulaminu)

## Ryzyka i pytania otwarte

- **Licencje mieszane:** ODbL z OSM wymusza udostępnianie pochodnych na tej samej licencji. Plan awaryjny: osobny zasób z danymi OSM, główny zbiór tylko ze źródeł na licencjach zgodnych z CC BY.
- **Brak rejestru państwowego:** jeśli nie dostaniemy danych z systemu ratownictwa, opieramy się na OSM + dane.gov.pl i pokazujemy kanał uploadu dla dysponentów.
- **Jakość godzin dostępności:** większość źródeł ma je jako wolny tekst; część rekordów dostanie `godziny_dostepnosci` = `nieznane` – do listy ograniczeń w prezentacji.
- **Limity API:** Overpass i Nominatim mają limity; cache na dysku i jednorazowe pobranie przed demem.
- Pytanie do organizatorów: czy dane.gov.pl ma już zalecany schemat lub harwester dla danych przestrzennych, z którym powinniśmy być zgodni?
- Pytanie do organizatorów: czy jest dostępny eksport z rejestru AED prowadzonego dla Państwowego Ratownictwa Medycznego?
- Pytanie do zespołu: kto jest właścicielem `schema/`, `ingest/` i `app/` (w `AGENTS.md` wciąż TODO)? Bez tego agenci nie mogą zacząć pracy w tych katalogach.
