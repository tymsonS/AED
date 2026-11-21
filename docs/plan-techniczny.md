# Misja AED – plan techniczny: schemat danych i skrypty zbierające

> Stan na 21.11.2026. Bieżące notatki i komentarze: [wersja robocza w Claude Docs](https://claude.ai/artifact/NKU5PW64Vx88gpswwQjN5g). Ten plik to wersja, na której się opieramy – poprawki wprowadzamy przez PR. Zasady pracy: [AGENTS.md](../AGENTS.md).

Budujemy **zestaw dla dostawców danych o AED**: wzorcowy zakres danych, walidator i generator pakietu, z którym gmina czy instytucja publikuje swoje AED na dane.gov.pl w jednym formacie i pod własną odpowiedzialnością. Adaptery zbierają dane z rozproszonych źródeł, ale tylko jako narzędzie robocze: mapę luk i podpowiedź dla dostawcy, gdzie sprawdzić AED. Kryterium „zgodność z dane.gov.pl” waży 30%, a „wzorcowy zakres danych” 10% – schemat, walidator i pakiet dostawcy są więc rdzeniem prototypu.

## Ustalenia z mentorami (21.11.2026)

1. **Problem:** dane o AED są rozproszone i niezweryfikowane – **nikt nie bierze za nie odpowiedzialności**. Samo zebranie map w jedną nie rozwiązuje problemu.
2. **Logotyp i hasło** służą akcji promocyjnej skierowanej do potencjalnych dostawców danych na dane.gov.pl, a nie do pitchu (obszar `branding/`).
3. **Nie publikujemy danych sami.** Portal ma swoje zasady i nie przebudowujemy go tak, żeby każdy mógł publikować. Zbiór musi mieć **dostawcę** (instytucję lub firmę), który bierze za niego odpowiedzialność. Mentorzy radzą zaglądać w kod źródłowy portalu.

Co to zmienia w planie:
- **Produktem jest zestaw dla dostawcy**, nie nasz zbiór: wzorcowy schemat, walidator, konwerter z dowolnego układu kolumn i metadane w formacie wymaganym przez portal. Dostawca (gmina, szpital, uczelnia, firma) publikuje AED na swoim koncie dane.gov.pl, w jednym formacie i pod własną odpowiedzialnością.
- **Nasz scalony zbiór (OSM + dane publiczne) to narzędzie, nie publikacja:**
  - **mapa luk** do kampanii: gdzie są AED bez odpowiedzialnego dostawcy;
  - **wstępne wypełnienie**: gmina widzi AED z OSM na swoim terenie, potwierdza je lub poprawia, dopisuje brakujące i eksportuje gotowy plik do publikacji. Potwierdzenie przez Profil Zaufany / mObywatel wiąże dane z osobą odpowiedzialną.
- **Precedens do sprawdzenia:** na dane.gov.pl setki deweloperów publikują ceny mieszkań w jednym formacie, według [instrukcji zasilania XML](https://assets.basehub.com/9f5f0c1c/c1aa71c8f576c4373a5fb048d901eaff/dane.gov.plinstrukcjazasilaniaxmldladeweloperow1.0.620251121v2.pdf). Ten sam model – wielu dostawców, jeden format – pasuje do AED.
- **Do sprawdzenia w kodzie portalu:** jak działa harwester (automatyczne zasilanie zbiorów) i profil metadanych [DCAT-AP-PL](https://dane.gov.pl/dcat-ap-pl/), żeby zestaw dla dostawcy generował pliki, które portal przyjmie bez poprawek.

### Druga rozmowa z mentorem (21.11.2026, po południu)

4. **Dane weryfikuje dystrybutor**, np. Centrum Ratownictwa, który zna urządzenia i ich właścicieli. Sami nie weryfikujemy AED.
5. **Pokazujemy AED zweryfikowane i niezweryfikowane razem**, ale z wyraźnym oznaczeniem. Nie ukrywamy danych z OSM, tylko zaznaczamy, że nikt za nie nie odpowiada.
6. **Dwie odpowiedzialności, dwie role.** Dystrybutor potwierdza, że AED jest w danym miejscu (lokalizacja). Właściciel urządzenia odpowiada za jego stan techniczny: baterię, elektrody, przeglądy. Rekord powinien mówić, kto zrobił jedno i drugie.
7. **Wyszukiwarka „jak paczkomaty InPost”.** Użytkownik widzi najbliższe AED od swojego położenia: listę z odległością, godzinami dostępności i statusem weryfikacji oraz przycisk trasy. Mapa jest dodatkiem, nie jedynym widokiem.

Co to zmienia w planie:
- **Mapa luk po gminach** (`python -m ingest gaps`, opis w `ingest/README.md`): dla każdej gminy liczba AED zweryfikowanych (poziom zaufania 1–2) i niezweryfikowanych (OSM), status gminy i AED poza obszarem dysponenta. To lista adresatów kampanii „zweryfikuj swój AED” dla dystrybutora, właścicieli urządzeń i gmin.
- **Oznaczenie w danych i na mapie:** poziom zaufania nie jest polem schematu ani eksportu. Wynika z pola `zrodlo` rekordu i wartości `poziom_zaufania` tego źródła w `ingest/sources.toml` (1–2 zweryfikowane, 3 niezweryfikowane). Do czasu eksportu dla `app/` (zadanie niżej) `app/` może go wyliczyć tak samo. W `app/` mapa musi odróżniać AED zweryfikowane od niezweryfikowanych (kolor i opis tekstowy, nie sam kolor – WCAG 2.2 AA).
- **Pakiet dostawcy dla dystrybutora:** ten sam pakiet co dla gminy, ale z listą AED do potwierdzenia na obszarze dystrybutora.
- **Pola o odpowiedzialności w schemacie (propozycja do decyzji właściciela `schema/`, osobne issue):** kto i kiedy potwierdził lokalizację, kto odpowiada za stan techniczny, `metoda_weryfikacji` = `dystrybutor` oraz `dostep` = `nieznany` dla rekordów bez tej informacji. Do czasu decyzji `ingest/` niczego w schemacie nie zmienia.
- **Wyszukiwarka w `app/` (Krystian):** lista najbliższych AED z odległością, godzinami („otwarte teraz” / „24/7” / „godziny nieznane”) i statusem weryfikacji opisanym tekstem. Dane: `ingest/data/out/aed.geojson`, a status weryfikacji z `zrodlo` + `ingest/sources.toml` jak wyżej.
- **Eksport dla `app/` (zadanie w `ingest/`):** osobny plik GeoJSON z dodatkową właściwością `poziom_zaufania` (i ewentualnie `zweryfikowany`), poza schematem wzorcowym. Wzorcowy `aed.csv` / `aed.geojson` i pakiet dostawcy zostają bez zmian, zgodne ze schematem.

## Architektura

Pipeline jest liniowy i idempotentny: każdy etap czyta wynik poprzedniego z dysku, więc można go uruchamiać i debugować osobno.

1. **Fetch** – adapter per źródło pobiera surowe dane do `data/raw/<source>/<data>.{json,csv,xlsx}` (bez modyfikacji, z zapisaną datą pobrania i URL-em).
2. **Map** – adapter mapuje rekordy źródła na wspólny model `AedRecord` (pydantic) i zapisuje `data/staged/<source>.parquet`.
3. **Normalize** – wspólne czyszczenie: adresy, telefony, godziny dostępności do składni `opening_hours`, współrzędne do WGS84 (EPSG:4326).
4. **Geocode / enrich** – brakujące współrzędne z adresu, brakujące kody TERYT ze współrzędnych.
5. **Deduplicate & merge** – łączenie tych samych urządzeń z różnych źródeł, z zachowaniem pochodzenia każdego pola.
6. **Validate** – walidacja względem schematu (Frictionless Table Schema + reguły biznesowe); raport błędów per źródło.
7. **Export** – `aed.csv` (UTF-8), `aed.geojson`, `aed.json`, `aed.xlsx` + metadane zbioru; to są zasoby, które **dostawca** publikuje na swoim koncie dane.gov.pl.

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

Poziom zaufania zapisujemy w `ingest/sources.toml` razem z id źródła, dysponentem, URL, licencją i częstotliwością odświeżania.

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
- **Adaptery:** jeden adapter dane.gov.pl z mapowaniem kolumn per zbiór w `sources.toml`, plus osobny adapter API Warszawy (token w `.env`).

### Ogólnopolska baza: OpenStreetMap / OpenAEDMap (rozpoznanie 21.11.2026)

Większość map AED w Polsce korzysta z tego samego źródła – OpenStreetMap. [OpenAEDMap](https://openaedmap.org) (projekt OpenStreetMap Polska) udostępnia eksport całego kraju jednym plikiem: `https://openaedmap.org/api/v1/countries/PL.geojson`. Na 21.11.2026 to **18 297 AED** – wobec 50 z dane.gov.pl. Warstwa „Defibrylatory” w [geoportal.gov.pl](https://www.geoportal.gov.pl) (GUGiK) też opiera się na danych OSM ([dziennikprawny.pl](https://www.dziennikprawny.pl/pl/a/wszystkie-zewnetrzne-defibrylatory-aed-w-polsce-na-jednej-mapie)). Według [Cardiomedico](https://cardiomedico.com/Mapa-AED-jak-znalezc-defibrylator-i-jak-zglosic-wlasny-AED-na-mape-blog-pol-1790894995.html) MSWiA potwierdziło w kwietniu 2026, że dyspozytorzy 112/997/998 widzą AED z OpenAEDMap – to źródło wtórne, do potwierdzenia u mentorów.

Wypełnienie pól w eksporcie (18 297 rekordów):

| Tag OSM | Pole schematu | Wypełnione |
| --- | --- | --- |
| `access` | `dostep` | 92,5% |
| `indoor` | `w_budynku` | 87,3% |
| `defibrillator:location` | `opis_lokalizacji` | 67,3% |
| `opening_hours` | `godziny_dostepnosci` | 37,1% |
| `operator` | `dysponent_nazwa` | 32,8% |
| `check_date` | `data_weryfikacji` | 32,7% |
| `phone` | `telefon_kontaktowy` | 24,5% |
| `level` | `kondygnacja` | 20,2% |

Wnioski:
- **OSM daje obraz całego kraju**, a źródła publiczne go weryfikują. Poziom zaufania OSM zostaje 3 (dane edytuje społeczność). Służy do mapy luk – gdzie są AED bez odpowiedzialnego dostawcy – i do podpowiedzi dla gminy, które urządzenia sprawdzić.
- **Adapter OpenAEDMap zamiast Overpass**: jeden plik GeoJSON z całą Polską, bez limitów zapytań Overpass.
- **Tylko narzędzie robocze:** portal dopuszcza wyłącznie licencje Creative Commons ([analiza kodu portalu](analiza-portalu-dane-gov-pl.md)), a dane OSM są na ODbL. Dlatego dane z OSM nie trafiają do pakietu dostawcy – służą do mapy luk i jako podpowiedź, gdzie dostawca ma sprawdzić AED w terenie.
- **Dane kontaktowe z OSM**: e-maili nie importujemy (schemat ich nie ma); telefony przyjmujemy tylko, gdy rekord ma `operator` (instytucję) – zgodnie z zakazem danych osobowych z `AGENTS.md`.

### Rejestry państwowe i inne mapy

- **Rejestr AED w Państwowym Ratownictwie Medycznym**: nie znaleźliśmy potwierdzenia, że istnieje ogólnopolski, publiczny rejestr. Ewidencja AED i połączenie z Systemem Wspomagania Dowodzenia PRM należą do kompetencji ministra zdrowia (wg Cardiomedico). Pytanie do mentorów: czy jest rejestr lub eksport, z którego możemy skorzystać.
- **Mapy prywatne i fundacji** ([Ratuj z Sercem](https://www.ratujzsercem.pl/), Fundacja Ratuj Życie / Staying Alive, mapa Warszawa 19115): dane zamknięte, bez zgody właściciela nie pobieramy. To potencjalni dysponenci, do których trafia kampania.

### Do znalezienia i potwierdzenia

- Portale otwartych danych miast i województw, które mają AED, ale nie opublikowały ich na dane.gov.pl.

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
  sources.toml                  # rejestr źródeł i mapowań kolumn (TOML)
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
- **dane.gov.pl:** wyszukiwanie zbiorów przez API, pobranie zasobów, zapis metadanych (dysponent, licencja, data modyfikacji). Kolumny mapujemy przez `sources.toml`, np. `Lokalizacja -> opis_lokalizacji`.
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
- **Metadane zbioru:** tytuł, opis, dysponent, licencja z listy portalu (domyślnie CC BY 4.0), częstotliwość aktualizacji, słowa kluczowe, kategoria. Przygotowujemy je w formacie zgodnym z DCAT-AP PL, jeśli portal to obsługuje dla harwestera.
- **Wzorcowy XLSX:** `schema/wzorcowy-zakres-danych-aed.xlsx` generowany ze schematu (#9) – spełnia wymóg formalny pliku z wzorcowym zakresem danych.

## Podział pracy i kolejność zadań

Schemat v0.1 jest na `main` (#13), pipeline z dane.gov.pl też (#14). Dalej jedno źródło przez cały pipeline, dopiero potem kolejne źródła. Dzięki temu po kilku godzinach mamy działający koniec-do-końca wynik do pokazania.

- [x] Schemat v0.1 (#13); otwarte: `id_aed` w szablonie dysponenta i wartość „nieznany” dla `dostep`
- [x] Szkielet `ingest/` + adapter dane.gov.pl: Przemyśl, Krosno, Marki (#14)
- [x] Adapter OpenAEDMap (`PL.geojson`, ~18 tys. AED) – ogólnopolskie pokrycie (#20)
- [ ] Adapter API Warszawy (token od mentorów w `.env`)
- [x] Pierwszy pełny przebieg: dane.gov.pl → normalize → validate → export CSV/GeoJSON (#14, 50 AED)
- [ ] Wyszukać portale miast i województw z danymi AED poza dane.gov.pl
- [x] Przejrzeć kod źródłowy dane.gov.pl: harwester, DCAT-AP-PL, wymagania dla zasobów (#18)
- [x] Eksport „pakietu dostawcy”: AED z wybranej gminy (OSM + dane publiczne) do weryfikacji i publikacji przez gminę (#19)
- [x] TERYT ze współrzędnych i mapa luk po gminach (`mikolaj/ingest-mapa-luk`)
- [ ] Geokodowanie brakujących współrzędnych z adresu
- [ ] Oznaczenie zweryfikowane / niezweryfikowane na mapie w `app/` (Krystian)
- [ ] Wyszukiwarka „najbliższe AED” jak paczkomaty InPost w `app/` (Krystian)
- [ ] Eksport GeoJSON dla `app/` z właściwością `poziom_zaufania` poza schematem wzorcowym (`ingest/`)
- [ ] Pola o odpowiedzialności w `schema/` – propozycja w issue, decyzja Krystiana; potem mapowanie w `ingest/`
- [ ] Deduplikacja i scalanie z `provenance`
- [ ] Walidator jako usługa dla dysponentów (upload CSV/XLSX → raport + poprawiony plik) w `app/`, zgodny z WCAG 2.2 AA i responsywny
- [ ] Raport walidacji i statystyki do prezentacji (liczba AED, pokrycie województw, % z godzinami dostępności)
- [ ] GitHub Actions z cronem odświeżającym zbiór
- [ ] Rejestr AI zgodnie z `AGENTS.md`: wpisy na bieżąco lokalnie w `docs/ai-usage/<imię>.md` (poza gitem), na koniec – na hasło „zbieramy rejestr AI” – PR z gałęzi `<imię>/ai-usage` do `docs/ai-usage.md` (wymóg §2 pkt 8 regulaminu)

## Dodawanie AED przez dysponentów i obywateli (etap późniejszy)

Teraz zbieramy istniejące bazy. W kolejnym etapie prototyp (`app/`) pozwala dodać lub poprawić AED – zgodnie z celem zadania, żeby dysponenci łatwo udostępniali dane w jednym formacie.

- **Formularz zgłoszenia** w wzorcowym zakresie danych, z tym samym walidatorem co pipeline; dysponent może też wgrać cały plik CSV/XLSX.
- **Potwierdzenie tożsamości przez Profil Zaufany lub mObywatel** (logowanie przez login.gov.pl / Węzeł Krajowy). Zgłoszenie podpisane przez osobę lub instytucję dostaje wyższy poziom zaufania niż anonimowe (poziom 2 – od dysponenta) i zapis, kto potwierdził dane.
- **Moderacja**: zgłoszenie anonimowe lub sprzeczne z danymi publicznymi trafia do kolejki przeglądu, zanim wejdzie do zbioru.
- Do sprawdzenia: warunki integracji z Węzłem Krajowym (dla prototypu wystarczy makieta przepływu) i czy zgłoszenia mogą wracać do OSM.

## Ryzyka i pytania otwarte

- **Brak rejestru państwowego:** jeśli nie dostaniemy danych z systemu ratownictwa, mapę luk budujemy z OSM + dane.gov.pl, a dane do publikacji przychodzą od dostawców przez pakiet dostawcy.
- **Jakość godzin dostępności:** większość źródeł ma je jako wolny tekst; część rekordów dostanie `godziny_dostepnosci` = `nieznane` – do listy ograniczeń w prezentacji.
- **Limity API:** Nominatim i API miast mają limity; OpenAEDMap daje jeden plik dla całej Polski. Cache na dysku i jednorazowe pobranie przed demem.
- Pytanie do mentorów: czy administratorzy portalu podłączają harwester XML dla małych dostawców (gmin) i ile to trwa? Szczegóły harwestera: `docs/analiza-portalu-dane-gov-pl.md`.
- Pytanie do mentorów: czy jest rejestr lub eksport AED z Państwowego Ratownictwa Medycznego i czy potwierdzają, że dyspozytorzy korzystają z OpenAEDMap?
- Pytanie do mentorów: token do API Warszawy.
- Pytanie do mentorów: kto mógłby być ogólnopolskim dostawcą zbioru AED (np. resort zdrowia, wojewodowie) i czy precedens deweloperów (jeden format, wielu dostawców) to dobry kierunek?
- Pytanie do zespołu: kto jest właścicielem `branding/` i `presentation/` (w `AGENTS.md` wciąż TODO)? Właścicielem `app/` jest Krystian (#21).
