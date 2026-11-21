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

## Źródła danych

Zaczynamy od dwóch źródeł z otwartym API (OSM i dane.gov.pl), bo dają ogólnopolskie pokrycie w pierwszych godzinach. Lista pochodzi z naszej wiedzy, nie z researchu – dostępność, licencję i format każdego źródła trzeba potwierdzić przed napisaniem adaptera.

| Priorytet | Źródło | Sposób pobrania | Licencja (do potwierdzenia) | Uwagi |
| --- | --- | --- | --- | --- |
| P0 | OpenStreetMap (`emergency=defibrillator`) | Overpass API, zapytanie po obszarze Polski | ODbL | Bogate tagi: `defibrillator:location`, `indoor`, `access`, `opening_hours`, `level`, `phone`, `operator` |
| P0 | Zbiory AED już obecne na dane.gov.pl (miasta, gminy) | API dane.gov.pl: wyszukiwanie „defibrylator”, „AED”, pobranie zasobów | zgodnie z metadanymi zbioru | Różne formaty i kolumny per dysponent – adapter generyczny + mapowania kolumn w YAML |
| P1 | Portale otwartych danych miast (np. Warszawa, Kraków, Gdańsk, Wrocław) | API / pliki CSV, GeoJSON, WMS/WFS | do sprawdzenia per miasto | Część może dublować to, co jest na dane.gov.pl |
| P1 | Rejestr AED prowadzony w systemie Państwowego Ratownictwa Medycznego | do ustalenia z organizatorem | do ustalenia | Najbardziej wiarygodne źródło dla służb; zapytać na stoisku dane.gov.pl / Discordzie |
| P2 | Aplikacje i mapy społeczne (fundacje, aplikacje ratunkowe) | eksport od właściciela | zwykle zamknięta | Bez zgody właściciela nie scrapujemy; w prototypie tylko jako przykład dysponenta |
| P2 | Dane od dysponentów (firmy, uczelnie, urzędy) | upload przez walidator w prototypie | wymagana otwarta, np. CC BY 4.0 | Kanał docelowy promowany kampanią i logotypem |

Każde źródło dostaje wpis w `ingest/sources.yaml`: id, nazwa dysponenta, URL, licencja, częstotliwość odświeżania, poziom zaufania (używany przy scalaniu).

## Wzorcowy schemat danych AED

Jeden wiersz = jedno urządzenie. Pola są w trzech poziomach: **wymagane** (bez nich rekord odrzucamy), **zalecane** (ostrzeżenie w walidatorze) i **opcjonalne**. Nazwy kolumn w snake_case po polsku bez znaków diakrytycznych, zgodnie z zasadą jednolitego nagłówka; w XLSX drugi arkusz „Słownik” opisuje każde pole, typ i dozwolone wartości.

| Grupa | Pole | Typ / format | Poziom | Opis i dozwolone wartości |
| --- | --- | --- | --- | --- |
| Identyfikacja | `id_aed` | UUID | wymagane | Globalny identyfikator nadawany przy scalaniu |
| Identyfikacja | `id_zrodlowe` | tekst | wymagane | Identyfikator u dysponenta danych |
| Identyfikacja | `numer_seryjny` | tekst | opcjonalne | Numer seryjny urządzenia, przydatny do deduplikacji |
| Lokalizacja | `szerokosc_geo`, `dlugosc_geo` | liczba, WGS84, 6 miejsc po przecinku | wymagane | Zakres dla Polski: 49,0–54,9 / 14,1–24,2 |
| Lokalizacja | `wojewodztwo`, `powiat`, `gmina` | tekst | zalecane | Nazwy z TERYT |
| Lokalizacja | `kod_teryt_gminy` | 7 znaków (TERC) | zalecane | Uzupełniane automatycznie ze współrzędnych |
| Lokalizacja | `miejscowosc`, `ulica`, `numer_budynku`, `kod_pocztowy` | tekst; kod `NN-NNN` | zalecane | Adres budynku |
| Lokalizacja | `nazwa_obiektu` | tekst | wymagane | Np. „Dworzec Centralny”, „Urząd Gminy X” |
| Lokalizacja | `opis_lokalizacji` | tekst | zalecane | Gdzie dokładnie wisi: „parter, przy recepcji, lewa ściana” |
| Lokalizacja | `kondygnacja` | liczba całkowita | opcjonalne | 0 = parter, ujemne = podziemia |
| Lokalizacja | `w_budynku` | tak / nie | zalecane | Wewnątrz czy na zewnątrz budynku |
| Dostępność | `dostep` | `publiczny` / `ograniczony` / `prywatny` | wymagane | Ograniczony = np. tylko w godzinach pracy, za recepcją |
| Dostępność | `godziny_dostepnosci` | składnia `opening_hours` (OSM) | wymagane | Np. `24/7`, `Mo-Fr 08:00-16:00` |
| Dostępność | `dostepny_24h` | tak / nie | wymagane | Pole pochodne, szybki filtr dla służb |
| Dostępność | `szafka_zamykana`, `kod_do_szafki_u_dyspozytora` | tak / nie | opcjonalne | Odpowiada na problem zamkniętych AED z opisu zadania |
| Urządzenie | `producent`, `model` | tekst | opcjonalne | |
| Urządzenie | `tryb_pediatryczny` | tak / nie / nieznane | zalecane | Elektrody lub tryb dla dzieci |
| Stan | `status` | `aktywny` / `w_serwisie` / `nieaktywny` / `nieznany` | wymagane | |
| Stan | `data_przegladu`, `data_waznosci_elektrod`, `data_waznosci_baterii` | data ISO 8601 | zalecane | Walidator ostrzega o datach w przeszłości |
| Dysponent | `dysponent_nazwa` | tekst | wymagane | Właściciel / zarządca urządzenia |
| Dysponent | `dysponent_regon` lub `dysponent_nip` | 9/14 lub 10 cyfr, z sumą kontrolną | zalecane | |
| Dysponent | `telefon_kontaktowy` | E.164, np. `+48221234567` | zalecane | Tylko numer instytucji (recepcja, ochrona), nigdy osoby prywatnej |
| Weryfikacja | `data_weryfikacji` | data ISO 8601 | wymagane | Kiedy ostatnio ktoś potwierdził, że AED jest na miejscu |
| Weryfikacja | `metoda_weryfikacji` | `dysponent` / `wizja_lokalna` / `zgloszenie_spoleczne` / `import` | zalecane | |
| Weryfikacja | `zdjecie_url` | URL | opcjonalne | |
| Metadane | `zrodlo` | id z `ingest/sources.yaml` | wymagane | Skąd pochodzi rekord (wymóg `AGENTS.md`); przy scalonym rekordzie: lista źródeł |
| Metadane | `licencja` | identyfikator, np. `CC-BY-4.0` | wymagane | |
| Metadane | `data_aktualizacji` | data i czas ISO 8601 | wymagane | Ostatnia zmiana rekordu |

Schemat trzymamy w jednym miejscu: `schema/aed.schema.json` (Frictionless Table Schema). Nie zawiera danych osobowych. Z niego generujemy wzorcowy XLSX, modele pydantic i dokumentację, żeby trzy artefakty się nie rozjechały.

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
- **Scalanie pól:** dla każdego pola wygrywa źródło o wyższym poziomie zaufania, przy remisie – nowsza `data_weryfikacji`. Pochodzenie każdego pola zapisujemy w tabeli `provenance` (id_aed, pole, źródło, wartość).
- **Stabilne `id_aed`:** UUID nadany raz i przechowywany w mapie `id_zrodlowe → id_aed`, żeby kolejne odświeżenia nie zmieniały identyfikatorów.

## Walidacja i publikacja zgodna z dane.gov.pl

Wynik pipeline'u musi być plikiem, który dysponent może wgrać na dane.gov.pl bez poprawek. Szczegółowe wymagania portalu sprawdzamy w [bazie wiedzy dane.gov.pl](https://dane.gov.pl/pl/knowledgebase/useful-materials) i [kodzie portalu](https://dane.gov.pl/source-code/) – poniższe to plan, nie potwierdzona lista.

- **Formaty:** CSV (UTF-8, przecinek, nagłówek w pierwszym wierszu), JSON, GeoJSON i XLSX. Żadnych PDF/DOC, zgodnie z wymogiem maszynowej czytelności.
- **Walidacja techniczna:** typy, formaty, słowniki wartości, wymagane pola – automatycznie ze schematu Frictionless.
- **Walidacja biznesowa:** współrzędne w Polsce i w gminie z `kod_teryt_gminy`, spójność `dostepny_24h` z `godziny_dostepnosci`, sumy kontrolne REGON/NIP, daty przeglądu i elektrod nie w przeszłości (ostrzeżenie), duplikaty `id_zrodlowe`.
- **Raport:** `validation_report.json` + czytelna wersja HTML: liczba błędów i ostrzeżeń per pole i per źródło. Zrzuty z raportu idą do prezentacji jako dowód spełnienia wymagań.
- **Metadane zbioru:** tytuł, opis, dysponent, licencja (proponujemy CC BY 4.0, przy danych z OSM osobny zasób na ODbL), częstotliwość aktualizacji, słowa kluczowe, kategoria. Przygotowujemy je w formacie zgodnym z DCAT-AP PL, jeśli portal to obsługuje dla harwestera.
- **Wzorcowy XLSX:** arkusz „Dane” z nagłówkami i listami rozwijanymi dla słowników, arkusz „Słownik”, arkusz „Przykład” z 3 poprawnymi rekordami. To spełnia wymóg formalny pliku z wzorcowym zakresem danych.

## Podział pracy i kolejność zadań

Najpierw schemat, potem jedno źródło przez cały pipeline, dopiero potem kolejne źródła. Dzięki temu po kilku godzinach mamy działający koniec-do-końca wynik do pokazania.

- [ ] Zamrozić v0.1 schematu: `schema/aed.schema.json` + wygenerowany wzorcowy XLSX
- [ ] Szkielet `ingest/`: `models.py`, `Adapter` bazowy, CLI
- [ ] Adapter OSM Overpass + fixture + test
- [ ] Pierwszy pełny przebieg: OSM → normalize → validate → export CSV/GeoJSON
- [ ] Adapter generyczny dane.gov.pl + mapowania 2–3 istniejących zbiorów AED
- [ ] Geokodowanie i TERYT
- [ ] Deduplikacja i scalanie z `provenance`
- [ ] Walidator jako usługa dla dysponentów (upload CSV/XLSX → raport + poprawiony plik) w prototypie
- [ ] Raport walidacji i statystyki do prezentacji (liczba AED, pokrycie województw, % z godzinami dostępności)
- [ ] GitHub Actions z cronem odświeżającym zbiór
- [ ] Wpisy w `docs/ai-usage/<imię>.md` na bieżąco, przed oddaniem połączone w jeden opis (wymóg §2 pkt 8 regulaminu)

## Ryzyka i pytania otwarte

- **Licencje mieszane:** ODbL z OSM wymusza udostępnianie pochodnych na tej samej licencji. Plan awaryjny: osobny zasób z danymi OSM, główny zbiór tylko ze źródeł na licencjach zgodnych z CC BY.
- **Brak rejestru państwowego:** jeśli nie dostaniemy danych z systemu ratownictwa, opieramy się na OSM + dane.gov.pl i pokazujemy kanał uploadu dla dysponentów.
- **Jakość godzin dostępności:** większość źródeł ma je jako wolny tekst; część rekordów zostanie z `godziny_dostepnosci` nieznanymi – do listy ograniczeń w prezentacji.
- **Limity API:** Overpass i Nominatim mają limity; cache na dysku i jednorazowe pobranie przed demem.
- Pytanie do organizatorów: czy dane.gov.pl ma już zalecany schemat lub harwester dla danych przestrzennych, z którym powinniśmy być zgodni?
- Pytanie do organizatorów: czy jest dostępny eksport z rejestru AED prowadzonego dla Państwowego Ratownictwa Medycznego?
- Pytanie do zespołu: kto jest właścicielem `schema/`, `ingest/` i `app/` (w `AGENTS.md` wciąż TODO)? Bez tego agenci nie mogą zacząć pracy w tych katalogach.
