# ingest/ – pobieranie i scalanie danych AED

Obszar Mikołaja (patrz `AGENTS.md`). Pipeline pobiera dane AED z rozproszonych źródeł, mapuje je na wzorcowy zakres danych z `schema/aed.schema.json`, normalizuje, waliduje i eksportuje do CSV i GeoJSON. Plan: `docs/plan-techniczny.md`.

## Uruchomienie

Wymaga Pythona 3.12. Pipeline korzysta tylko z biblioteki standardowej. Walidacja XSD pakietu dostawcy wymaga opcjonalnie `xmlschema` (`pip install xmlschema`), która nie jest jeszcze w pliku zależności.

```bash
python -m ingest sources          # lista źródeł z ingest/sources.toml
python -m ingest fetch all        # pobiera surowe dane do ingest/data/raw/
python -m ingest build all        # mapuje, normalizuje i zapisuje ingest/data/out/
python -m ingest validate         # waliduje ingest/data/out/aed.csv względem schema/
python -m ingest fetch-gminy      # jednorazowo: granice gmin z PRG (GUGiK), ok. 2 min
python -m ingest gaps             # mapa luk po gminach -> ingest/data/out/mapa-luk.*
python -m ingest dystrybutor --obszar 18 --dystrybutor "Centrum Ratownictwa …"   # lista AED do potwierdzenia
python -m ingest wczytaj-dystrybutora ingest/data/pakiety/dystrybutor-18/do-potwierdzenia.csv --dystrybutor "Centrum Ratownictwa …"
python -m ingest stats            # statystyki do prezentacji -> ingest/data/out/statystyki.json, .md
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
| `dystrybutor` | dystrybutor, np. Centrum Ratownictwa | 0 (lokalne) | AED potwierdzone przez dystrybutora, poziom zaufania 2; pliki dodaje `wczytaj-dystrybutora`, opis niżej |
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
- **Bez granic gmin weryfikacja jest niepełna.** Nie wykryjemy AED poza obszarem dysponenta, więc np. AED z Marek ze współrzędnymi w Krośnie dostanie w `aed-app.geojson` status `zweryfikowany`. `build`, `stats` i `dystrybutor` wypisują wtedy ostrzeżenie. Przed budową danych dla `app/` uruchom raz `python -m ingest fetch-gminy`.
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

## Statystyki do prezentacji

`python -m ingest stats` zapisuje `ingest/data/out/statystyki.json` i `statystyki.md`. W pliku MD są gotowe tabele do slajdów i dla zespołu `presentation/`: najważniejsze liczby, źródła, jakość danych (wszystkie, zweryfikowane i niezweryfikowane), pokrycie województw i najczęstsze problemy walidacji. Liczymy urządzenia, nie wpisy: duplikat OSM liczy się raz. Reguły są te same co w mapie luk (`gaps.verification()`). Pokrycie gmin wymaga granic (`fetch-gminy`).

Wynik (21.11.2026):
- **18 304 AED**, z czego **49 zweryfikowanych** (0,3%). Pominięto 43 duplikaty OSM.
- AED w danych ma 2 128 z 2 479 gmin (85,8%), ale dane na dane.gov.pl publikują tylko 3 gminy. W 686 gminach są AED, ale przy żadnym nie ma dysponenta.
- Wśród niezweryfikowanych 32,9% ma dysponenta, a 17,7% sprawdzono w ostatnim roku. Godziny dostępności ma 37,1%, a 24/7 publicznie dostępnych jest 19,7%.
- **Adres (miejscowość) ma tylko 0,4% AED z OSM**, bo w OSM adres ma 76 z 18 297 punktów. Bez geokodowania odwrotnego albo danych od dysponentów lista nie powie, pod jakim adresem szukać AED.
- Walidacja liczy **wpisy** (z duplikatami OSM), a nie urządzenia. Błędy to braki pól wymaganych w danych OSM: `data_weryfikacji` (12 302), `dysponent_nazwa` (12 291), `nazwa_obiektu` (12 000). Brak REGON/NIP to tylko ostrzeżenie (18 347). Co najmniej jeden błąd ma 17 278 z 18 347 wpisów (94,2%), łącznie 36 593 błędy. Brak `dostep` jest od #31 ostrzeżeniem (`dostep` = `nieznany`, 1 436).
- Przy zbiorach z dane.gov.pl `data_weryfikacji` to data danych zasobu, a nie sprawdzenie urządzenia. Raport ma o tym przypis pod tabelą jakości.

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
- **Priorytet:** 1 – niezweryfikowany bez dysponenta albo punkt instytucji poza jej gminą (najpewniej błąd w danych); 2 – niezweryfikowany, nigdy niesprawdzony albo sprawdzony ponad 12 miesięcy temu (data z przyszłości to literówka, też 2); 3 – niezweryfikowany, sprawdzony w ostatnich 12 miesiącach; 4 – zweryfikowany przez instytucję. Na liście sortujemy po gminie, miejscowości i priorytecie, żeby dało się sprawdzać w terenie po kolei.
- **Kolumny dla dystrybutora:** `wynik_sprawdzenia` (`potwierdzam` / `inne_miejsce` / `brak_urzadzenia` / `nie_sprawdzono`), `data_sprawdzenia`, `lokalizacje_potwierdzil`, `odpowiedzialny_za_stan_techniczny`, `dysponent_poprawiony`, `nazwa_obiektu_poprawiona` (w wierszach z OSM wymagana, bo nazw z OSM nie publikujemy), `uwagi_dystrybutora`. Nazwy dwóch pól o odpowiedzialności są takie jak w schemacie v0.2 (#27). Kolumny zostawiamy puste – nic nie potwierdzamy za dystrybutora.
- **Licencja:** lista to podpowiedź, nie publikacja, więc zawiera dane OSM z atrybucją ODbL. Do publikacji na dane.gov.pl służy pakiet dostawcy.
- **Formuły w Excelu:** teksty z OSM może edytować każdy, a lista trafia do instytucji. Komórka zaczynająca się od `=`, `+`, `-`, `@`, tabulatora lub CR dostaje na początku apostrof (`excel_safe()`), więc Excel nie wykona jej jako formuły.
- **Przykład (21.11.2026), województwo podkarpackie (`--obszar 18`):** 1 313 AED do sprawdzenia, w tym 42 zweryfikowane; 951 z priorytetem 1 (950 bez dysponenta i AED z Marek leżący w Krośnie), 292 niesprawdzane od ponad roku lub nigdy, 28 sprawdzonych w ostatnim roku; pominięto 39 duplikatów OSM.
### Wczytanie wypełnionej listy

`python -m ingest wczytaj-dystrybutora <plik.csv> --dystrybutor "<instytucja>"` zamienia wypełnioną listę na rekordy we wzorcowym zakresie danych. Wynik trafia do katalogu `wczytane/` obok pliku:

| Plik | Zawartość |
|---|---|
| `potwierdzone.csv`, `.geojson` | AED z wynikiem `potwierdzam` albo `inne_miejsce`, z `metoda_weryfikacji` = `dystrybutor`, `lokalizacje_potwierdzil` i `data_weryfikacji` = `data_sprawdzenia` |
| `do-usuniecia.csv` | AED z wynikiem `brak_urzadzenia`: dla gminy lub społeczności OSM, z `id_zrodlowe` (np. `node/…`) i uwagami |
| `raport-wczytania.json` | liczby, problemy z numerem wiersza jak w Excelu i wynik walidacji potwierdzonych rekordów |

- **Licencja (review #29):** z wiersza OSM do zbioru CC trafia tylko to, co dystrybutor potwierdził albo wpisał sam: lokalizacja, `lokalizacje_potwierdzil`, data, `odpowiedzialny_za_stan_techniczny`, `dysponent_poprawiony` i `nazwa_obiektu_poprawiona`. Nazwa, opis, adres, godziny i dostęp z OSM nie przechodzą. Zamiast nich wpisujemy `nieznany`/`nieznane` do czasu danych od właściciela. Gminę i województwo wyliczamy sami z granic PRG. Takie rekordy mają `zrodlo` = `dystrybutor` i licencję z `--licencja` (domyślnie `CC-BY-4.0`).
- **Wiersze instytucji** (licencja CC) zachowują pola z oryginalnego rekordu. Dostają `zrodlo` = np. `danegovpl-krosno;dystrybutor` i swoją licencję.
- **Kontrola:** `id_aed` i `zrodlo` muszą pasować do AED z bieżących danych, a ten sam AED nie może wystąpić dwa razy. `data_sprawdzenia` nie może być z przyszłości. Przy `inne_miejsce` wymagane są nowe współrzędne, a gminę wyliczamy wtedy od nowa. Wiersz z OSM bez `nazwa_obiektu_poprawiona` albo `dysponent_poprawiony` przechodzi z uwagą, ale walidacja pokaże brak pola wymaganego.
- **Plik z Excela:** UTF-8 albo Windows-1250, przecinek albo średnik, data `RRRR-MM-DD` albo `DD.MM.RRRR`, przecinek dziesiętny we współrzędnych. Apostrof dodany przez `excel_safe()` jest zdejmowany.
### Potwierdzone AED w całym pipelinie

Wczytanie kopiuje wynik do `ingest/data/raw/dystrybutor/`: `resource-<obszar>--<dystrybutor>.csv` z potwierdzonymi i `usuniete-<obszar>--<dystrybutor>.csv`, np. `resource-dystrybutor-18--centrum-ratownictwa-x.csv`. Stamtąd czyta je źródło `dystrybutor` z `sources.toml` (poziom zaufania 2, `opcjonalne`, `wszystkie_pliki`). Ponowne wczytanie listy **tego samego dystrybutora** dla tego samego obszaru zastępuje poprzednie, a listy dwóch dystrybutorów z jednego obszaru leżą obok siebie. Bez wczytanych list `build` działa jak dotąd.

**Osobne źródło dla dystrybutora (opcjonalnie):** wszystkie potwierdzenia mają `zrodlo` = `dystrybutor`, a różni je `lokalizacje_potwierdzil`. Na prototyp to wystarcza. Żeby w zbiorze było widać, czyje dane trafiły, dodaj do `sources.toml` kopię wpisu `dystrybutor` z innym `id`, np. `dystrybutor-cr-krakow`, i wczytuj z `--zrodlo dystrybutor-cr-krakow`.

Przy następnym `build`, `gaps`, `stats` i `dystrybutor`:
- **jeden rekord na `id_aed`** (`gaps.supersede()`): potwierdzony rekord ma to samo `id_aed` co wpis z OSM albo z dane.gov.pl i go zastępuje. Wygrywa wyższy poziom zaufania, a przy remisie rekord z `lokalizacje_potwierdzil`, więc kolejność źródeł nie ma znaczenia. AED przeniesiony (`inne_miejsce`) jest tylko w nowym miejscu;
- **zgłoszony brak urządzenia (`brak_urzadzenia`):**
  - wpis społeczny (OSM) znika z mapy luk, statystyk i `aed-app.geojson`;
  - rekordu instytucji nie usuwamy na podstawie zgłoszenia o niższym poziomie zaufania, bo gmina dalej go publikuje. Rekord przestaje być zweryfikowany, w `aed-app.geojson` ma opis „Dystrybutor zgłosił brak urządzenia (kto, kiedy). Do wyjaśnienia z dysponentem: …”, a na liście dla dystrybutora priorytet 1;
- **poziom zaufania rekordu z kilku źródeł** (`danegovpl-krosno;dystrybutor`) to najwyższy z nich (`gaps.trust_level()`);
- **`aed-app.geojson`:** `opis_weryfikacji` = „Lokalizację potwierdził: … (data).”;
- **lista dla dystrybutora:** potwierdzone AED mają priorytet 4 i powód „lokalizację potwierdził …”.

Próba na Krośnie: 3 potwierdzone (1 z gminy, 2 z OSM, w tym 1 w innym miejscu) i 1 do usunięcia. Wynik: zweryfikowanych 49 → 51, AED 18 304 → 18 303, bez powtórzonych `id_aed`. Ponowne wczytanie daje ten sam wynik, a pakiet dostawcy dla Krosna się nie zmienia.

## Struktura

| Plik | Rola |
|---|---|
| `cli.py` | polecenia `sources`, `fetch`, `build`, `validate`, `package`, `dystrybutor`, `stats`, `gaps`, `fetch-gminy`, `fetch-xsd` |
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
| `distributor_import.py` | wczytanie wypełnionej listy: potwierdzone rekordy bez treści z OSM, AED do usunięcia, raport |
| `adapters/dystrybutor.py` | źródło `dystrybutor`: czyta wczytane listy z `raw/dystrybutor/` i AED do usunięcia |
| `stats.py` | statystyki do prezentacji: JSON i tabele Markdown |
| `fields.py` | lista pól ze `schema/aed.schema.json` (v0.2, 41 pól); `FALLBACK_FIELDS` to kopia zapasowa, którą test porównuje ze schematem |

## Decyzje mapowania

- `godziny_dostepnosci` i `dostepny_24h` = `nieznane`, `status` = `nieznany`: żaden z trzech zbiorów tego nie podaje.
- `data_weryfikacji` = data danych zasobu na dane.gov.pl, `metoda_weryfikacji` = `import`, `dostep` = `nieznany`.
- `dysponent_nazwa` = instytucja publikująca zbiór (zwykle też zarządca urządzeń).
- Telefon tylko instytucji, w formacie E.164. E-maile i strony WWW ze źródeł pomijamy – schemat ich nie przewiduje.

## Schemat v0.2

`ingest/` działa według `schema/` v0.2 (#27):
- `dostep` = `nieznany`, gdy źródło nie podaje dostępu. Dotyczy wszystkich zbiorów z dane.gov.pl, a w OSM punktów bez tagu `access` lub z nieznaną wartością. Walidator daje ostrzeżenie, nie błąd. Dzięki temu wszystkie 50 rekordów z dane.gov.pl przechodzi walidację bez błędów (wcześniej każdy miał błąd), a pakiet dostawcy dla Krosna ma 0 błędów w tym, co walidator sprawdza (bez typów pól, zob. niżej).
- `lokalizacje_potwierdzil` wypełniamy tylko wtedy, gdy rejestr źródeł mówi to wprost: klucz `lokalizacje_potwierdzil = "…"` przy źródle w `sources.toml`. Samo opublikowanie zbioru nie jest potwierdzeniem, że urządzenie jest na miejscu, więc zbiory gmin mają `metoda_weryfikacji` = `import` i puste `lokalizacje_potwierdzil`. Potwierdzenie ma przyjść od dystrybutora (lista z `python -m ingest dystrybutor`).
- `odpowiedzialny_za_stan_techniczny` zostawiamy puste, czyli według schematu odpowiada `dysponent_nazwa`. Żadne źródło tego nie podaje.
- Walidator ma reguły v0.2 ze `schema/README.md`: ostrzeżenie przy `dostep` = `nieznany` i przy `metoda_weryfikacji` = `dystrybutor`/`dysponent` bez `lokalizacje_potwierdzil`. Druga reguła nie dotyczy dziś żadnego rekordu, bo zbiory z dane.gov.pl mają `import`, a OSM `zgloszenie_spoleczne`. Ostrzeżenie pojawi się dopiero przy danych od dysponenta albo z listy dystrybutora.
- `w_budynku` (OSM `indoor`) = `tak`/`nie`, jak w schemacie (`boolean`, `trueValues` `tak`). Wcześniej `true`/`false` w ok. 87% punktów OSM.
- **Typy pól:** walidator sprawdza wymagalność, słowniki, wzorce i zakresy, a także typy i formaty ze schematu:
  - `integer` (`kondygnacja`);
  - `boolean` z `trueValues`/`falseValues` (`tak`/`nie`);
  - `date` (`RRRR-MM-DD`, prawdziwa data);
  - `datetime` (ISO 8601 z sekundami i strefą, np. `2026-11-21T12:00:00Z`);
  - `uuid` (`id_aed`) i `uri` (`zdjecie_url`, tylko `http(s)://`);
  - ograniczenie `unique` (`id_aed`).

  Na danych z 21.11.2026 nie przybyło żadnego błędu, bo adaptery już normalizują te pola. Stary błąd `w_budynku` = `true`/`false` (poprawiony w #31) dałby teraz 15 969 błędów.

  **Nigdy łagodniej niż frictionless**, bo dostawca zobaczyłby fałszywe „0 błędów”, a portal albo pełna walidacja według schematu odrzuciłyby plik. W trzech miejscach walidator `ingest/` jest **celowo surowszy od samego schematu**. To nie jest błąd:
  - `data_aktualizacji` bez strefy (`2026-11-21T12:00:00`) albo ze spacją zamiast `T`: błąd, bo opis pola wymaga strefy;
  - `id_aed` wielkimi literami albo bez łączników: błąd, bo `id_aed` nadaje system w zapisie kanonicznym;
  - `zdjecie_url` z `ftp://` albo `mailto:`: błąd, bo adres zdjęcia ma być stroną `http(s)://`.

  Liczbę całkowitą ze spacją (`" 3"`) przyjmujemy tak jak frictionless, a daty i wartości logiczne ze spacją odrzucamy, też jak frictionless. Pilnuje tego test `TestZgodnoscZFrictionless`: porównuje werdykty obu walidatorów, gdy frictionless jest zainstalowany (`pip install "frictionless>=5.21,<5.22"`, jak w `schema/`), a bez niego jest pomijany.
