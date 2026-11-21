# ingest/ – pobieranie i scalanie danych AED

Obszar Mikołaja (patrz `AGENTS.md`). Pipeline pobiera dane AED z rozproszonych źródeł, mapuje je na wzorcowy zakres danych z `schema/aed.schema.json`, normalizuje, waliduje i eksportuje do CSV i GeoJSON. Plan: `docs/plan-techniczny.md`.

## Uruchomienie

Wymaga Pythona 3.12. Na razie tylko biblioteka standardowa – bez dodatkowych zależności.

```bash
python -m ingest sources          # lista źródeł z ingest/sources.toml
python -m ingest fetch all        # pobiera surowe dane do ingest/data/raw/
python -m ingest build all        # mapuje, normalizuje i zapisuje ingest/data/out/
python -m ingest validate         # waliduje ingest/data/out/aed.csv względem schema/
python -m ingest fetch-gminy      # jednorazowo: granice gmin z PRG (GUGiK), ok. 2 min
python -m ingest gaps             # mapa luk po gminach -> ingest/data/out/mapa-luk.*
python -m ingest dystrybutor --obszar 18 --dystrybutor "Centrum Ratownictwa …"   # lista AED do potwierdzenia
python -m ingest fetch-xsd        # jednorazowo: XSD harwestera z kodu portalu (ok. 90 MB pobrania)
python -m ingest package danegovpl-krosno --teryt 1861011 --gmina "Krosno"     --dostawca "Urząd Miasta Krosna" --base-url https://example.krosno.pl/dane/aed/
python -m unittest discover -s ingest/tests -t .   # testy bez sieci
```

Zamiast `all` można podać id źródła, np. `danegovpl-krosno`. Katalog `ingest/data/` jest poza gitem.

Wynik w `ingest/data/out/`: `aed.csv` (UTF-8, separator `,`), `aed.geojson`, `aed-app.geojson` (dla `app/`, opis niżej), `validation_report.json`. Walidacja uruchamia się, gdy w repo jest `schema/aed.schema.json`.

## Źródła

Rejestr źródeł: `sources.toml` – id, dysponent, zasób, format, licencja, poziom zaufania i mapowanie kolumn. Nowy zbiór z dane.gov.pl w podobnym formacie to nowy wpis w rejestrze, bez nowego kodu.

| id | Dysponent | Rekordy (21.11.2026) | Uwagi |
|---|---|---|---|
| `danegovpl-przemysl` | Urząd Miejski w Przemyślu | 21 | GeoJSON, adres w osobnych polach, zdjęcie |
| `danegovpl-krosno` | Urząd Miasta Krosna | 21 | CSV, adres w jednej kolumnie |
| `danegovpl-marki` | Urząd Miasta Marki | 8 | CSV z całymi wierszami w cudzysłowie; w 7 z 8 wierszy współrzędne zamienione względem nagłówka – adapter to wykrywa, naprawia i zapisuje ostrzeżenie |
| `osm-openaedmap` | Społeczność OpenStreetMap (OpenAEDMap) | 18 297 | eksport całej Polski jednym plikiem GeoJSON; licencja ODbL, poziom zaufania 3 – tylko narzędzie robocze (mapa luk, podpowiedź dla dostawcy), nie trafia do pakietu dostawcy |


### Co mówią dane z OpenAEDMap (21.11.2026, 18 297 AED)

Liczby potwierdzają problem wskazany przez mentorów: dane są niezweryfikowane i nikt nie bierze za nie odpowiedzialności.

| Miara | AED | Udział |
|---|---|---|
| bez wskazanego dysponenta (`operator`) | 12 291 | 67,2% |
| bez daty weryfikacji (`check_date`) | 12 302 | 67,2% |
| zweryfikowane ponad 12 miesięcy temu | 2 771 | 15,1% |
| bez godzin dostępności | 11 520 | 63,0% |
| publicznie dostępne 24/7 | 3 602 | 19,7% |

Mapowanie tagów OSM: `access` → `dostep` (yes/permissive → publiczny, customers/permit → ograniczony, private/no → prywatny), `opening_hours` → `godziny_dostepnosci`, `indoor` → `w_budynku`, `level` → `kondygnacja`, `defibrillator:location` → `opis_lokalizacji`, `operator` → `dysponent_nazwa`, `check_date` → `data_weryfikacji`. Telefon pobieramy tylko wtedy, gdy rekord ma `operator`, czyli instytucję. Bez operatora numer może należeć do osoby prywatnej. E-maili nie pobieramy.

Warszawa (dane.gov.pl 39512) wymaga osobnego adaptera: zasób na dane.gov.pl prowadzi do strony katalogu, a dane są tylko w API `dane.um.warszawa.pl` z tokenem (token w `.env`).

## Mapa luk po gminach

`python -m ingest gaps` pokazuje stan danych o AED w każdej z 2 479 gmin. To lista adresatów kampanii „zweryfikuj swój AED”: dla dystrybutora (np. Centrum Ratownictwa), właścicieli urządzeń i gmin.

- **Granice gmin:** z Państwowego Rejestru Granic (WFS GUGiK, warstwa `A03_Granice_gmin`, kod TERYT w `JPT_KOD_JE`). `fetch-gminy` zapisuje je w `ingest/data/prg/gminy.json` (poza gitem), uproszczone do ok. 20 m.
- **Uzupełnianie rekordów:** gdy granice są pobrane, każdy rekord dostaje `kod_teryt_gminy`, `gmina` i `wojewodztwo`. Przypisanie 18 tys. punktów trwa poniżej sekundy.
- **Zweryfikowane i niezweryfikowane:** zweryfikowane to źródła z poziomem zaufania 1–2, czyli za które odpowiada instytucja. Niezweryfikowane to OSM. Punkt OSM do 50 m od zweryfikowanego liczy się jako ten sam AED, a nie drugi. To typowy przypadek dwóch wpisów przy dwóch wejściach.
- **AED poza obszarem dysponenta:** źródło z polem `teryt` w `sources.toml` jest sprawdzane, czy jego punkty leżą w gminie dysponenta. Punkt spoza gminy dostaje ostrzeżenie i nie liczy się jako zweryfikowany. Przykład: w zbiorze Marek jeden AED ma dokładnie współrzędne pływalni w Krośnie, prawdopodobnie skopiowane z pliku Krosna.
- **Wynik:**
  - `mapa-luk.csv`: wiersz na gminę, ze statusem, liczbą AED zweryfikowanych i niezweryfikowanych, AED z dysponentem, AED sprawdzonymi w ostatnich 12 miesiącach, publicznymi 24/7, gęstością i zbiorem na dane.gov.pl;
  - `mapa-luk.geojson`: granice gmin uproszczone do ok. 300 m, z tymi samymi danymi, do mapy w `app/`;
  - `mapa-luk-podsumowanie.json`: podsumowanie w podziale na województwa.

### Wynik (21.11.2026)

| Status gminy | Gminy |
|---|---|
| publikuje dane (zbiór na dane.gov.pl) | 3 |
| tylko dane niezweryfikowane (OSM) | 2 125 |
| brak AED w danych | 351 |

- 18 251 AED niezweryfikowanych wobec 49 zweryfikowanych.
- Tylko 32,9% niezweryfikowanych ma wskazanego dysponenta, a 17,7% sprawdzono w ostatnich 12 miesiącach.
- W 686 gminach są AED, ale przy żadnym nie ma dysponenta.
- Najwięcej gmin bez AED w danych: mazowieckie (79 z 314), lubelskie (60 z 213), podlaskie (38 z 119).
- „Brak AED w danych” nie musi oznaczać braku AED w gminie. To miejsce, gdzie nikt ich nie zgłosił.

## Eksport dla app/

`python -m ingest build all` zapisuje też `ingest/data/out/aed-app.geojson`, czyli wszystkie AED dla mapy i wyszukiwarki w `app/`. To **nie jest plik wzorcowy**: ma tylko pola schematu potrzebne mapie i wyszukiwarce (lista od Krystiana w #25: `id_aed`, adres, `nazwa_obiektu`, `opis_lokalizacji`, `dostep`, `godziny_dostepnosci`, `status`, `dysponent_nazwa`, `telefon_kontaktowy`, `zrodlo`, `licencja`; współrzędne w `geometry`) oraz właściwości spoza schematu. Pełne rekordy są w `aed.geojson`. Na dane.gov.pl trafiają tylko `aed.csv` / `aed.geojson` i pakiet dostawcy.

| Właściwość | Typ | Znaczenie |
|---|---|---|
| `poziom_zaufania` | liczba 1–3 | z `sources.toml` według pola `zrodlo`: 1 – administracja publiczna, 2 – od dysponenta, 3 – dane społeczne (OSM); nieznane źródło = 3 |
| `status_weryfikacji` | tekst | `zweryfikowany` (poziom 1–2 i punkt w gminie dysponenta) / `niezweryfikowany`, etykieta do pokazania obok koloru (WCAG 2.2 AA) |
| `opis_weryfikacji` | tekst | jedno zdanie dla użytkownika, np. „Dane instytucji: Urząd Miasta Krosna.” albo „Dane społeczne – … Żadna instytucja nie potwierdziła tego AED.”; osobne zdanie dla punktu instytucji leżącego poza jej gminą |
| `ten_sam_co` | tekst | dla punktu OSM do 50 m od zweryfikowanego: `id_aed` zweryfikowanego AED; `app/` może taki punkt ukryć, żeby nie pokazywać tego samego AED dwa razy |

Reguły są takie same jak w mapie luk (`gaps.verification()`), więc liczby się zgadzają. Na 21.11.2026: 18 347 AED, z czego 49 zweryfikowanych, 1 poza obszarem dysponenta i 43 punkty OSM pokrywające się ze zweryfikowanymi. Plik ma ok. 12,6 MB (zapis bez wcięć, współrzędne do 6 miejsc), a po kompresji gzip, którą serwery stron statycznych robią same, ok. 1,2 MB. Rekord bez poprawnych współrzędnych nie trafia do pliku i nie potwierdza punktów obok.

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

## Pakiet dla dystrybutora

`python -m ingest dystrybutor --obszar <TERYT…> --dystrybutor "<instytucja>"` tworzy w `ingest/data/pakiety/dystrybutor-<TERYT>/` listę AED do potwierdzenia na obszarze dystrybutora, np. Centrum Ratownictwa. Zgodnie z ustaleniami z mentorem dystrybutor potwierdza lokalizację, a za stan techniczny odpowiada właściciel. Obszar to jeden lub kilka kodów TERYT: 2 cyfry (województwo), 4 (powiat) albo 7 (gmina). Polecenie wymaga granic gmin (`fetch-gminy`).

| Plik | Zawartość |
|---|---|
| `do-potwierdzenia.csv` | lista robocza: wiersz na AED z priorytetem, powodem, linkiem do mapy i pustymi kolumnami do wypełnienia; UTF-8 z BOM, żeby Excel pokazał polskie znaki |
| `do-potwierdzenia.geojson` | te same punkty do wczytania na mapę |
| `podsumowanie.json` | liczby dla obszaru i dla każdej gminy, gminy z największą liczbą AED bez dysponenta na początku |
| `CZYTAJ-MNIE.txt` | co wypełnić, wartości do wyboru, atrybucja OSM |

- **Co jest na liście:** AED ze wszystkich źródeł, zweryfikowane i niezweryfikowane. Punkt OSM, który jest tym samym AED co zweryfikowany (`ten_sam_co`), pomijamy, bo dystrybutor sprawdza urządzenie, a nie wpis. Reguły są te same co w mapie luk i `aed-app.geojson` (`gaps.verification()`).
- **Priorytet:** 1 – niezweryfikowany bez dysponenta; 2 – niezweryfikowany, nigdy niesprawdzony albo sprawdzony ponad 12 miesięcy temu; 3 – niezweryfikowany, sprawdzony w ostatnich 12 miesiącach; 4 – zweryfikowany przez instytucję. Na liście sortujemy po gminie, miejscowości i priorytecie, żeby dało się sprawdzać w terenie po kolei.
- **Kolumny dla dystrybutora:** `wynik_sprawdzenia` (`potwierdzam` / `inne_miejsce` / `brak_urzadzenia` / `nie_sprawdzono`), `data_sprawdzenia`, `lokalizacje_potwierdzil`, `odpowiedzialny_za_stan_techniczny`, `dysponent_poprawiony`, `uwagi_dystrybutora`. Nazwy dwóch pól o odpowiedzialności są takie jak w schemacie v0.2 (#27). Kolumny zostawiamy puste – nic nie potwierdzamy za dystrybutora.
- **Licencja:** lista to podpowiedź, nie publikacja, więc zawiera dane OSM z atrybucją ODbL. Do publikacji na dane.gov.pl służy pakiet dostawcy.
- **Przykład (21.11.2026), województwo podkarpackie (`--obszar 18`):** 1 313 AED do sprawdzenia, w tym 42 zweryfikowane; 950 bez dysponenta (priorytet 1), 293 niesprawdzane od ponad roku lub nigdy, 28 sprawdzonych w ostatnim roku; pominięto 39 duplikatów OSM.
- **Dalej:** wczytanie wypełnionej listy z powrotem (`metoda_weryfikacji` = `dystrybutor`, `lokalizacje_potwierdzil`, `data_weryfikacji`), gdy schemat v0.2 będzie na `main`.

## Struktura

| Plik | Rola |
|---|---|
| `cli.py` | polecenia `sources`, `fetch`, `build`, `validate` |
| `adapters/base.py` | klasa `Adapter`: `fetch()` → `parse()` → `map_record()` |
| `adapters/danegovpl.py` | zbiory z dane.gov.pl: CSV i GeoJSON, metadane zasobu z API |
| `adapters/openaedmap.py` | eksport OpenAEDMap (OSM) dla całej Polski, mapowanie tagów OSM |
| `normalize.py` | współrzędne, adresy, telefony, stabilne `id_aed` (UUID5 z `zrodlo` + `id_zrodlowe`) |
| `validate.py` | ograniczenia ze schematu + część reguł biznesowych z `schema/README.md` |
| `export.py` | CSV, GeoJSON, raport JSON |
| `gminy.py` | granice gmin z PRG, przypisanie punktów do gmin (TERYT) |
| `gaps.py` | mapa luk: status gminy, zweryfikowane i niezweryfikowane AED, AED poza obszarem dysponenta |
| `package.py` | pakiet dostawcy: XML harwestera, MD5, walidacja XSD, instrukcja |
| `distributor.py` | lista AED do potwierdzenia dla dystrybutora: priorytet, kolumny do wypełnienia, podsumowanie po gminach |
| `fields.py` | lista pól (ze schematu, a do czasu scalenia `schema/` – kopia zapasowa pilnowana testem) |

## Decyzje mapowania

- `godziny_dostepnosci` i `dostepny_24h` = `nieznane`, `status` = `nieznany`: żaden z trzech zbiorów tego nie podaje.
- `data_weryfikacji` = data danych zasobu na dane.gov.pl, `metoda_weryfikacji` = `import`.
- `dysponent_nazwa` = instytucja publikująca zbiór (zwykle też zarządca urządzeń).
- Telefon tylko instytucji, w formacie E.164. E-maile i strony WWW ze źródeł pomijamy – schemat ich nie przewiduje.

## Otwarte sprawy (do właściciela `schema/`)

- **`dostep` jest wymagane, a słownik nie ma wartości „nieznany”.** Żaden zbiór z dane.gov.pl nie podaje dostępności, więc dziś wszystkie 50 rekordów ma błąd walidacji. Propozycja: dodać `nieznany` do słownika, tak jak przy `status`.
- Rejestr źródeł to `ingest/sources.toml` (TOML czyta biblioteka standardowa), a nie `sources.yaml` z planu i `schema/README.md`.
