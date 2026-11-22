# Misja AED – plan techniczny i stan realizacji

> Plan z 21.11.2026, zaktualizowany 22.11.2026 do stanu kodu na `main`. Zasady pracy: [AGENTS.md](../AGENTS.md). Szczegóły poszczególnych części są w README katalogów (`schema/`, `ingest/`, `app/`, `portal/`, `branding/`).

Budujemy **zestaw dla dostawców danych o AED**: wzorcowy zakres danych, walidator i generator pakietu, z którym gmina czy instytucja publikuje swoje AED na dane.gov.pl w jednym formacie i pod własną odpowiedzialnością, oraz **wykaz zbiorczy AED w kodzie portalu**, który skleja zasoby wielu dostawców w jedną listę. Adaptery zbierają dane z rozproszonych źródeł, ale tylko jako narzędzie robocze: mapę luk i podpowiedź dla dostawcy, gdzie sprawdzić AED. Kryterium „zgodność z dane.gov.pl” waży 30%, a „wzorcowy zakres danych” 10% – schemat, walidator, pakiet dostawcy i wykaz w portalu są więc rdzeniem prototypu.

## Ustalenia z mentorami (21.11.2026)

1. **Problem:** dane o AED są rozproszone i niezweryfikowane – **nikt nie bierze za nie odpowiedzialności**. Samo zebranie map w jedną nie rozwiązuje problemu.
2. **Logotyp i hasło** służą akcji promocyjnej skierowanej do potencjalnych dostawców danych na dane.gov.pl, a nie do pitchu (obszar `branding/`).
3. **Nie publikujemy danych sami.** Portal ma swoje zasady i nie przebudowujemy go tak, żeby każdy mógł publikować. Zbiór musi mieć **dostawcę** (instytucję lub firmę), który bierze za niego odpowiedzialność. Mentorzy radzą zaglądać w kod źródłowy portalu.

Co z tego wynikło:
- **Produktem jest zestaw dla dostawcy**, nie nasz zbiór: wzorcowy schemat (`schema/`), walidator i pakiet dostawcy z plikiem dla harwestera XML portalu (`python -m ingest package`). Dostawca publikuje AED na swoim koncie dane.gov.pl.
- **Nasz scalony zbiór (OSM + dane publiczne) to narzędzie, nie publikacja:** mapa luk do kampanii (`python -m ingest gaps`) i lista AED do sprawdzenia dla dystrybutora (`python -m ingest dystrybutor`).
- **Precedens:** na dane.gov.pl setki deweloperów publikują ceny mieszkań w jednym formacie, według [instrukcji zasilania XML](https://assets.basehub.com/9f5f0c1c/c1aa71c8f576c4373a5fb048d901eaff/dane.gov.plinstrukcjazasilaniaxmldladeweloperow1.0.620251121v2.pdf). Ten sam model – wielu dostawców, jeden format – przyjęliśmy dla AED.
- **Kod portalu przejrzany** ([analiza-portalu-dane-gov-pl.md](analiza-portalu-dane-gov-pl.md)): harwester XML, licencje (tylko CC), podgląd na mapie. Pakiet dostawcy generuje XML zgodny z oryginalnym XSD portalu 1.13.
- **Potwierdzenie tożsamości przez Profil Zaufany / mObywatel – nie realizujemy** (decyzja po rozmowie z mentorami). Tożsamość dostawcy potwierdza sam portal przy logowaniu.

### Druga rozmowa z mentorem (21.11.2026, po południu)

4. **Dane weryfikuje dystrybutor**, np. Centrum Ratownictwa, który zna urządzenia i ich właścicieli. Sami nie weryfikujemy AED.
5. **Pokazujemy AED zweryfikowane i niezweryfikowane razem**, ale z wyraźnym oznaczeniem. Nie ukrywamy danych z OSM, tylko zaznaczamy, że nikt za nie nie odpowiada.
6. **Dwie odpowiedzialności, dwie role.** Dystrybutor potwierdza, że AED jest w danym miejscu (lokalizacja). Właściciel urządzenia odpowiada za jego stan techniczny: baterię, elektrody, przeglądy. Rekord powinien mówić, kto zrobił jedno i drugie.
7. **Wyszukiwarka „jak paczkomaty InPost”.** Użytkownik widzi najbliższe AED od swojego położenia: listę z odległością, godzinami dostępności i statusem weryfikacji oraz przycisk trasy. Mapa jest dodatkiem, nie jedynym widokiem.

Co z tego wynikło:
- **Mapa luk po gminach** (`python -m ingest gaps`): dla każdej z 2 479 gmin liczba AED zweryfikowanych i niezweryfikowanych, status gminy i AED poza obszarem dysponenta.
- **Oznaczenie zweryfikowany / niezweryfikowany:** wynika z pola `zrodlo` i wartości `poziom_zaufania` źródła w `ingest/sources.toml` (1–2 zweryfikowane, 3 niezweryfikowane) oraz z położenia punktu w gminie dysponenta. Eksport `aed-app.geojson` ma właściwości `poziom_zaufania`, `status_weryfikacji` i `opis_weryfikacji` poza schematem wzorcowym; `app/` pokazuje etykietę tekstową i znak ✓, nie sam kolor (WCAG 2.2 AA).
- **Pakiet dla dystrybutora** (`python -m ingest dystrybutor`, `wczytaj-dystrybutora`): lista AED do potwierdzenia na jego obszarze i wczytanie wyników – potwierdzone AED stają się zweryfikowane.
- **Pola o odpowiedzialności w schemacie v0.2:** `lokalizacje_potwierdzil`, `odpowiedzialny_za_stan_techniczny`, `metoda_weryfikacji` = `dystrybutor` oraz `dostep` = `nieznany` (`schema/README.md`, „Kto za co odpowiada”).
- **Wyszukiwarka w `app/`:** najbliższe AED z odległością w linii prostej, pieszo i samochodem, godzinami („dostępny teraz” / „24/7” / „godziny nieznane”), statusem weryfikacji i przyciskiem trasy.

### Podpowiedź mentora: „wykazy” w portalu (21.11.2026, wieczór)

8. **Zbiorcza tabela w portalu, a nie tylko poza nim.** Dane mają być zasobami wielu dostawców na dane.gov.pl, a portal ma z nich składać jedną standardową listę, tak jak istniejące „wykazy”. Najważniejsze jest przebudowanie logiki portalu. Trzeba też postawić portal lokalnie (z panelem administracyjnym), a kod portalu dodać do repo jako pierwszy commit.

Co z tego wynikło: wzorem jest **Wykaz Główny DGA** ([analiza-wykazow-portalu.md](analiza-wykazow-portalu.md)). Kod portalu jest w `portal/` (pierwszy commit = oryginał 2.63.0), a nasza zmiana dodaje flagę zasobu „Zawiera wykaz defibrylatorów AED” i codzienne zadanie, które skleja takie zasoby w jeden zasób „Wykaz zbiorczy defibrylatorów AED” z oznaczeniem możliwych duplikatów. Sprawdzone na portalu uruchomionym lokalnie w dockerze: prawdziwe pakiety 3 gmin dają wykaz 50 AED ([`portal/README-AED.md`](../portal/README-AED.md), [`portal/README-DOCKER-AED.md`](../portal/README-DOCKER-AED.md)).

## Architektura

```
źródła (dane.gov.pl, OpenAEDMap, listy dystrybutora, pliki dostawców)
   │  python -m ingest fetch      → ingest/data/raw/<źródło>/
   ▼
ingest/  build: mapowanie na wzorcowy zakres, normalizacja, gminy z PRG, scalanie
   │     → ingest/data/out/: aed.csv, aed.geojson (wzorcowe), aed-app.geojson (dla app/),
   │       validation_report.json; gaps, stats, dystrybutor – narzędzia robocze
   ├─► package  → ingest/data/pakiety/aed-<TERYT>/ – pakiet dostawcy (CSV, GeoJSON, XML harwestera, MD5)
   │                └─► dostawca publikuje na dane.gov.pl → portal/ skleja zasoby z flagą AED
   │                    w „Wykaz zbiorczy defibrylatorów AED”
   └─► app/scripts/build_data.py → app/data/aed-data.js – prototyp „Znajdź AED”
```

Każdy etap czyta wynik poprzedniego z dysku, więc można go uruchamiać osobno. Pipeline `ingest/` korzysta tylko z biblioteki standardowej Pythona 3.12; do testów potrzebne są `frictionless`, `openpyxl`, `pytest` i `xmlschema`.

Interfejs `app/` spełnia wymagania z treści zadania: WCAG 2.2 AA (audyt axe-core na 14 widokach, test kontrastu), responsywność mobile first i język polski (`app/README.md`).

## Źródła danych

Zbiór ma pokrywać **całą Polskę**. Najważniejsze są źródła zweryfikowane – rządowe i samorządowe – i to one wygrywają przy scalaniu. Same jednak nie pokryją kraju, więc luki uzupełniamy źródłami społecznymi, wyraźnie oznaczonymi jako niezweryfikowane. Docelowo luki zamyka kampania AEDane: każdy dysponent publikuje w jednym wzorcowym formacie (`schema/`).

### Poziomy zaufania

| Poziom | Typ źródła | Źródła w `sources.toml` | Rola przy scalaniu |
| --- | --- | --- | --- |
| 1 – zweryfikowane | Dane administracji publicznej | `danegovpl-przemysl`, `danegovpl-krosno`, `danegovpl-marki` | Wygrywa przy konflikcie |
| 2 – od dysponenta | Dane potwierdzone przez dystrybutora albo przygotowane przez dostawcę | `dystrybutor`, `plik-dostawcy` | Wygrywa z poziomem 3 |
| 3 – społeczne | Mapy tworzone przez społeczność | `osm-openaedmap` (`metoda_weryfikacji` = `zgloszenie_spoleczne`) | Uzupełnia pokrycie kraju; nie trafia do pakietu dostawcy (licencja ODbL) |

Poziom zaufania jest zapisany w `ingest/sources.toml` razem z id źródła, dysponentem, zasobem, licencją i mapowaniem kolumn.

### Co jest na dane.gov.pl (rozpoznanie 21.11.2026)

Wyszukiwanie w API dane.gov.pl („defibrylator”, „defibrylatory”, „AED”) zwraca tylko **4 zbiory z lokalizacjami AED** – wszystkie od urzędów miast, każdy w innym formacie:

| Zbiór (id) | Dysponent | Rekordy | Format i stan | Licencja |
| --- | --- | --- | --- | --- |
| [Lokalizacja defibrylatorów (AED)](https://dane.gov.pl/pl/dataset/39512) (39512) | Urząd m.st. Warszawy | – | Zasób „JSON” prowadzi do strony katalogu Warszawy; dane tylko przez API `dane.um.warszawa.pl` z tokenem użytkownika | CC BY 4.0 |
| [Lokalizacje AED w Przemyślu](https://dane.gov.pl/pl/dataset/4581) (4581) | Urząd Miejski w Przemyślu | 21 | GeoJSON/CSV/JSON/XML; adres rozbity na pola; zamiast zdjęć ten sam znak „AED” przy każdym urządzeniu; brak godzin | CC0 1.0 |
| [Defibrylatory w Mieście Krosno](https://dane.gov.pl/pl/dataset/3624) (3624) | Urząd Miasta Krosna | 21 | CSV: długość, szerokość, nazwa, lokalizacja, adres, id | CC0 1.0 |
| [Defibrylatory na terenie Miasta Marki](https://dane.gov.pl/pl/dataset/4955) (4955) | Urząd Miasta Marki | 8 | CSV/XLSX o tych samych kolumnach co Krosno, ale każdy wiersz w cudzysłowie i **współrzędne zamienione względem nagłówka**; jeden punkt ma współrzędne pływalni w Krośnie | CC BY 4.0 |

Wnioski:
- **Pokrycie:** 4 miasta z 2 479 gmin. To najmocniejszy argument za wzorcowym zakresem danych i kampanią.
- **Brak standardu:** te same informacje w czterech różnych układach, z błędami. Adapter `danegovpl` czyta trzy z nich przez mapowanie kolumn w `sources.toml`, wykrywa zamienione współrzędne, a mapa luk wykrywa punkt spoza gminy dysponenta.
- **Warszawa** wymaga osobnego adaptera API z tokenem – nie zrealizowano.

### Ogólnopolska baza: OpenStreetMap / OpenAEDMap

[OpenAEDMap](https://openaedmap.org) (projekt OpenStreetMap Polska) udostępnia eksport całego kraju jednym plikiem: `https://openaedmap.org/api/v1/countries/PL.geojson`. Na 22.11.2026 to **18 310 AED** – wobec 50 z dane.gov.pl. Warstwa „Defibrylatory” w [geoportal.gov.pl](https://www.geoportal.gov.pl) (GUGiK) też opiera się na danych OSM ([dziennikprawny.pl](https://www.dziennikprawny.pl/pl/a/wszystkie-zewnetrzne-defibrylatory-aed-w-polsce-na-jednej-mapie)).

Wypełnienie pól w eksporcie (rozpoznanie 21.11.2026, 18 297 rekordów):

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
- **OSM daje obraz całego kraju**, a źródła publiczne go weryfikują. Poziom zaufania OSM to 3 (dane edytuje społeczność).
- **Tylko narzędzie robocze:** portal dopuszcza wyłącznie licencje Creative Commons, a dane OSM są na ODbL. Dane z OSM nie trafiają do pakietu dostawcy ani do wykazu w portalu – służą do mapy luk, listy dla dystrybutora i mapy w `app/` (z atrybucją ODbL).
- **Dane kontaktowe z OSM:** e-maili nie importujemy; telefony tylko, gdy rekord ma `operator` (instytucję) – zgodnie z zakazem danych osobowych z `AGENTS.md`.

### Rejestry państwowe i inne mapy

- **Rejestr AED w Państwowym Ratownictwie Medycznym:** nie znaleźliśmy potwierdzenia, że istnieje ogólnopolski, publiczny rejestr.
- **Mapy prywatne i fundacji** ([Ratuj z Sercem](https://www.ratujzsercem.pl/), Fundacja Ratuj Życie / Staying Alive, mapa Warszawa 19115): dane zamknięte, bez zgody właściciela nie pobieramy. To potencjalni dysponenci, do których trafia kampania.

## Wzorcowy schemat danych AED

Źródłem prawdy jest `schema/aed.schema.json` (Frictionless Table Schema v0.2, 41 pól: 14 wymaganych, 20 zalecanych, 7 opcjonalnych). Ten plan nie powiela listy pól; zasady i decyzje są w [`schema/README.md`](../schema/README.md).

- **Jeden wiersz = jedno urządzenie.** Nazwy kolumn w snake_case po polsku bez znaków diakrytycznych.
- **Brakujące godziny:** `godziny_dostepnosci` przyjmuje `nieznane`, a `dostepny_24h` wartości `tak` / `nie` / `nieznane`.
- **`id_aed` nadaje system:** w pliku od dysponenta pole zostaje puste; `ingest/` liczy je jako UUID5 z pary `zrodlo` + `id_zrodlowe`, więc jest stałe między odświeżeniami.
- **`data_aktualizacji`:** czas polski bez strefy (np. `2026-11-21T13:00:00`) – tylko taki zapis przyjmują dane tabelaryczne dane.gov.pl (decyzja z #61).
- **Bez danych osobowych:** `telefon_kontaktowy`, `lokalizacje_potwierdzil` i `odpowiedzialny_za_stan_techniczny` to wyłącznie instytucje.
- **Jedno źródło, wiele artefaktów:** ze schematu generujemy wzorcowy XLSX (`schema/build_xlsx.py`: arkusze „Dane”, „Słownik”, „Przykład”), a `ingest/fields.py` czyta z niego listę pól. Zmiana nazwy lub typu pola wymaga zgody właścicieli `ingest/` i `app/`.

## Pipeline `ingest/`

Python 3.12, tylko biblioteka standardowa. Polecenia (`python -m ingest …`) i struktura plików: [`ingest/README.md`](../ingest/README.md). Nowy zbiór z dane.gov.pl w podobnym układzie to nowy wpis w `sources.toml` z mapowaniem kolumn, bez nowego kodu.

- **Adaptery** (`ingest/adapters/`): `danegovpl` (CSV i GeoJSON z dane.gov.pl, metadane zasobu z API), `openaedmap` (eksport OSM dla Polski), `dystrybutor` (wczytane listy dystrybutora), `wzorcowy-csv` (pliki dostawców).
- **Normalizacja** (`normalize.py`): współrzędne WGS84 w granicach Polski z wykrywaniem zamienionych lat/lon, adres z jednej kolumny rozbity na pola, telefony do E.164, `id_aed` jako UUID5. Pliki z Excela (`csvio.py`): Windows-1250 lub UTF-8, średnik, daty `DD.MM.RRRR`, przecinek dziesiętny, zera obcięte z przodu w TERYT, REGON i NIP.
- **Gminy** (`gminy.py`): granice z Państwowego Rejestru Granic (WFS GUGiK), przypisanie `kod_teryt_gminy`, `gmina` i `wojewodztwo` ze współrzędnych, bez zewnętrznych bibliotek.
- **Scalanie** (`gaps.py`): jeden rekord na `id_aed` – wygrywa wyższy poziom zaufania, przy remisie rekord z potwierdzoną lokalizacją; punkt OSM do 50 m od zweryfikowanego to ten sam AED (`ten_sam_co`), a nie drugi; rekord z kilku źródeł ma w `zrodlo` ich identyfikatory rozdzielone `;`.
- **Zdjęcia:** ten sam plik przy wielu AED jednego źródła (np. ikona zamiast zdjęcia miejsca) jest pomijany.
- **Testy:** na fixture'ach bez sieci (`python -m pytest schema ingest`).

## Walidacja i publikacja zgodna z dane.gov.pl

Wynik pipeline'u to pakiet, który dostawca może wgrać na dane.gov.pl bez poprawek – sprawdzone na portalu uruchomionym lokalnie (`portal/README-DOCKER-AED.md`, „Demo”).

- **Formaty:** CSV (UTF-8, przecinek, nagłówek w pierwszym wierszu) i GeoJSON, a dla harwestera XML z sumą MD5. Żadnych PDF/DOC.
- **Walidacja techniczna** (`ingest/validate.py`): wymagane pola, typy, formaty, słowniki, zakresy i unikalność ze schematu. Nigdy łagodniej niż biblioteka `frictionless` – pilnuje tego test porównujący werdykty obu walidatorów.
- **Walidacja biznesowa:** część reguł ze `schema/README.md` (spójność `dostepny_24h` z godzinami, `dostep` = `nieznany`, brak REGON i NIP, potwierdzenie bez `lokalizacje_potwierdzil`, powtórzone `id_zrodlowe`); punkt spoza gminy dysponenta wykrywa mapa luk. Które reguły nie są jeszcze sprawdzane – `schema/README.md`.
- **Raport:** `validation_report.json` (cały zbiór) i `raport-walidacji.json` w pakiecie dostawcy – liczba błędów i ostrzeżeń z polem i numerem rekordu.
- **Metadane zbioru:** w `aed.xml` dla harwestera (schemat 1.13, kategoria `HEAL`, TERYT, licencja z listy portalu, domyślnie CC BY 4.0), walidowane oryginalnym XSD portalu.
- **Wzorcowy XLSX:** `schema/wzorcowy-zakres-danych-aed.xlsx` – wymóg formalny zadania.

## Stan realizacji (22.11.2026)

Zrobione:
- [x] Wzorcowy zakres danych v0.2 z polami o odpowiedzialności i wzorcowy XLSX (`schema/`)
- [x] Adaptery dane.gov.pl (Przemyśl, Krosno, Marki) i OpenAEDMap – ogólnopolskie pokrycie
- [x] Normalizacja, przypisanie gmin z PRG, scalanie po `id_aed` i punktów OSM do 50 m
- [x] Walidator zgodny z frictionless, raport walidacji i statystyki do prezentacji (`python -m ingest stats`)
- [x] Mapa luk po gminach (`python -m ingest gaps`)
- [x] Pakiet dostawcy z XML harwestera zgodnym z XSD portalu, także z pliku z Excela (`package --plik`)
- [x] Lista dla dystrybutora i wczytanie wyników, z regułą „usunięcie AED instytucji dopiero po powiadomieniu dysponenta”
- [x] Eksport dla `app/` z poziomem zaufania i statusem weryfikacji
- [x] Prototyp „Znajdź AED”: wyszukiwarka jak paczkomaty, oznaczenie zweryfikowany / niezweryfikowany, trasy, podstrona AED, audyt WCAG 2.2 AA
- [x] Kod portalu w repo, portal lokalnie w dockerze, wykaz zbiorczy AED na wzór DGA i demo jedną komendą (`portal/aed_demo.sh`)
- [x] Logotyp, księga znaku i hasło akcji AEDane (`branding/`)

Nie zrealizowane (ograniczenia prototypu):
- [ ] Adapter API Warszawy (wymaga tokenu)
- [ ] Portale miast i województw z danymi AED poza dane.gov.pl
- [ ] Geokodowanie: adres → współrzędne i współrzędne → adres (adres ma tylko ok. 0,4% AED z OSM)
- [ ] Część reguł biznesowych walidatora (składnia `opening_hours`, sumy kontrolne REGON/NIP, terminy przeglądów – lista w `schema/README.md`)
- [ ] Walidator jako usługa w przeglądarce (upload CSV/XLSX); dziś pakiet z pliku robi `python -m ingest package --plik`
- [ ] Automatyczne odświeżanie zbioru (np. GitHub Actions z cronem)
- [ ] Flaga AED w XSD harwestera (`containsAedData`) i w API portalu – dziś flagę zaznacza się w panelu

Poza zakresem (decyzja zespołu): formularz zgłoszeń od obywateli i potwierdzanie tożsamości przez Profil Zaufany / mObywatel.

## Ryzyka i pytania otwarte

- **Brak rejestru państwowego:** mapę luk budujemy z OSM + dane.gov.pl, a dane do publikacji przychodzą od dostawców przez pakiet dostawcy.
- **Jakość godzin dostępności:** godziny ma ok. 37% AED; gdy ich nie ma, `app/` nie obiecuje dostępności. Zbiory gmin z dane.gov.pl nie podają godzin wcale – nawet zweryfikowany AED nie trafia wtedy do „dostępny teraz”.
- **Publiczne usługi w prototypie** (trasy FOSSGIS, Nominatim, kafelki OSM, zdjęcia OpenAEDMap): wystarczają na prototyp, przy wdrożeniu potrzebne własne serwery.
- Pytanie do mentorów: kto ma być właścicielem zbioru „Wykaz zbiorczy defibrylatorów AED” na portalu (lokalnie „Pierwsza instytucja”)?
- Pytanie do mentorów: czy administratorzy portalu podłączają harwester XML dla małych dostawców (gmin) i ile to trwa?
