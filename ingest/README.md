# ingest/ – pobieranie i scalanie danych AED

Obszar Mikołaja (patrz `AGENTS.md`). Pipeline pobiera dane AED z rozproszonych źródeł, mapuje je na wzorcowy zakres danych z `schema/aed.schema.json`, normalizuje, waliduje i eksportuje do CSV i GeoJSON. Plan: `docs/plan-techniczny.md`.

## Uruchomienie

Wymaga Pythona 3.12. Na razie tylko biblioteka standardowa – bez dodatkowych zależności.

```bash
python -m ingest sources          # lista źródeł z ingest/sources.toml
python -m ingest fetch all        # pobiera surowe dane do ingest/data/raw/
python -m ingest build all        # mapuje, normalizuje i zapisuje ingest/data/out/
python -m ingest validate         # waliduje ingest/data/out/aed.csv względem schema/
python -m ingest fetch-xsd        # jednorazowo: XSD harwestera z kodu portalu (ok. 90 MB pobrania)
python -m ingest package danegovpl-krosno --teryt 1861011 --gmina "Krosno"     --dostawca "Urząd Miasta Krosna" --base-url https://example.krosno.pl/dane/aed/
python -m unittest discover -s ingest/tests -t .   # testy bez sieci
```

Zamiast `all` można podać id źródła, np. `danegovpl-krosno`. Katalog `ingest/data/` jest poza gitem.

Wynik w `ingest/data/out/`: `aed.csv` (UTF-8, separator `,`), `aed.geojson`, `validation_report.json`. Walidacja uruchamia się, gdy w repo jest `schema/aed.schema.json`.

## Źródła

Rejestr źródeł: `sources.toml` – id, dysponent, zasób, format, licencja, poziom zaufania i mapowanie kolumn. Nowy zbiór z dane.gov.pl w podobnym formacie to nowy wpis w rejestrze, bez nowego kodu.

| id | Dysponent | Rekordy (21.11.2026) | Uwagi |
|---|---|---|---|
| `danegovpl-przemysl` | Urząd Miejski w Przemyślu | 21 | GeoJSON, adres w osobnych polach, zdjęcie |
| `danegovpl-krosno` | Urząd Miasta Krosna | 21 | CSV, adres w jednej kolumnie |
| `danegovpl-marki` | Urząd Miasta Marki | 8 | CSV z całymi wierszami w cudzysłowie; w 7 z 8 wierszy współrzędne zamienione względem nagłówka – adapter to wykrywa, naprawia i zapisuje ostrzeżenie |

Warszawa (dane.gov.pl 39512) wymaga osobnego adaptera: zasób na dane.gov.pl prowadzi do strony katalogu, a dane są tylko w API `dane.um.warszawa.pl` z tokenem (token w `.env`).

## Pakiet dostawcy

`python -m ingest package` tworzy w `ingest/data/pakiety/aed-<TERYT>/` komplet plików, które dostawca, np. gmina, publikuje na dane.gov.pl na swoim koncie i pod własną odpowiedzialnością. Wymagania portalu opisuje `docs/analiza-portalu-dane-gov-pl.md`.

| Plik | Zawartość |
|---|---|
| `aed.csv`, `aed.geojson` | zasoby we wzorcowym zakresie danych |
| `aed.xml` | opis zbioru dla harwestera XML portalu (`urn:otwarte-dane:harvester:1.13`, kategoria `HEAL`, TERYT, licencja CC) |
| `aed.md5` | suma kontrolna `aed.xml`, wymagana przez harwester |
| `raport-walidacji.json` | braki względem schematu, czyli co dostawca musi uzupełnić przed publikacją |
| `CZYTAJ-MNIE.txt` | instrukcja publikacji: automatycznie przez harwester albo ręcznie |

- **Walidacja XSD:** `aed.xml` jest walidowany względem oryginalnego XSD portalu, tą samą biblioteką co portal (`xmlschema`). XSD pobiera `fetch-xsd` do `ingest/data/xsd/`, poza gitem, bo kod portalu jest na GPL v3. Bez XSD lub biblioteki pakiet powstaje, ale bez walidacji. Biblioteka: `pip install xmlschema` (zależność do dopisania osobnym PR).
- **Licencje:** pakiet przyjmuje tylko licencje z listy portalu (7 licencji CC). Rekordy na ODbL, czyli z OpenStreetMap, są odrzucane.
- **Wymagania portalu:** TERYT ma 2, 4 albo 7 cyfr, adres musi być `https://`.
- **Szkic:** `--szkic` daje status `draft` zamiast `published`.

## Struktura

| Plik | Rola |
|---|---|
| `cli.py` | polecenia `sources`, `fetch`, `build`, `validate` |
| `adapters/base.py` | klasa `Adapter`: `fetch()` → `parse()` → `map_record()` |
| `adapters/danegovpl.py` | zbiory z dane.gov.pl: CSV i GeoJSON, metadane zasobu z API |
| `normalize.py` | współrzędne, adresy, telefony, stabilne `id_aed` (UUID5 z `zrodlo` + `id_zrodlowe`) |
| `validate.py` | ograniczenia ze schematu + część reguł biznesowych z `schema/README.md` |
| `export.py` | CSV, GeoJSON, raport JSON |
| `package.py` | pakiet dostawcy: XML harwestera, MD5, walidacja XSD, instrukcja |
| `fields.py` | lista pól (ze schematu, a do czasu scalenia `schema/` – kopia zapasowa pilnowana testem) |

## Decyzje mapowania

- `godziny_dostepnosci` i `dostepny_24h` = `nieznane`, `status` = `nieznany`: żaden z trzech zbiorów tego nie podaje.
- `data_weryfikacji` = data danych zasobu na dane.gov.pl, `metoda_weryfikacji` = `import`.
- `dysponent_nazwa` = instytucja publikująca zbiór (zwykle też zarządca urządzeń).
- Telefon tylko instytucji, w formacie E.164. E-maile i strony WWW ze źródeł pomijamy – schemat ich nie przewiduje.

## Otwarte sprawy (do właściciela `schema/`)

- **`dostep` jest wymagane, a słownik nie ma wartości „nieznany”.** Żaden zbiór z dane.gov.pl nie podaje dostępności, więc dziś wszystkie 50 rekordów ma błąd walidacji. Propozycja: dodać `nieznany` do słownika, tak jak przy `status`.
- Rejestr źródeł to `ingest/sources.toml` (TOML czyta biblioteka standardowa), a nie `sources.yaml` z planu i `schema/README.md`.
