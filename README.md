# AEDane – dane o defibrylatorach AED na dane.gov.pl

**Misja AED – Dane na ratunek** · HackNation 2026 · zadanie Ministerstwa Cyfryzacji ([treść zadania](docs/zadanie-misja-aed.md), [regulamin](docs/regulamin-misja-aed.md))

> **Otwarte dane. Cenne sekundy. Uratowane życie.** Udostępnij dane o swoim defibrylatorze na dane.gov.pl.

## Dla jury: jak sprawdzić w 5 minut

| Co | Gdzie |
|---|---|
| **Prototyp „Znajdź AED”** | `cd app && python -m http.server 8000` → <http://localhost:8000> (bez instalacji i budowania, dane są w repo; lokalizacja działa na `localhost`) |
| **Wzorcowy zakres danych (XLSX)** | [`schema/wzorcowy-zakres-danych-aed.xlsx`](schema/wzorcowy-zakres-danych-aed.xlsx) – arkusze „Dane”, „Słownik”, „Przykład” |
| **Logotyp** | [`branding/logotyp-aedane.svg`](branding/logotyp-aedane.svg), [`.png`](branding/logotyp-aedane.png), [`.jpg`](branding/logotyp-aedane.jpg), [`.pdf`](branding/logotyp-aedane.pdf) |
| **Księga znaku** | [`branding/ksiega-znaku-aedane.pdf`](branding/ksiega-znaku-aedane.pdf) – koncepcja, hasło, kolory, pole ochronne, minimalna wielkość, niedozwolone użycie |
| **Prezentacja** | [`presentation/aedane-prezentacja.pdf`](presentation/aedane-prezentacja.pdf) – 10 slajdów: problem, rozwiązanie, kroki użytkowników, ograniczenia |
| **Wykaz zbiorczy w portalu dane.gov.pl** | demo jedną komendą: [`portal/README-DOCKER-AED.md`](portal/README-DOCKER-AED.md#demo-wykaz-zbiorczy-aed-jedną-komendą) – 3 gminy → jeden wykaz 50 AED (docker, ok. 20 GB dysku); opis zmian: [`portal/README-AED.md`](portal/README-AED.md) |

**Testy jednym poleceniem** (Python 3.12 i Node.js, z głównego katalogu):

```bash
pip install "frictionless>=5,<6" openpyxl pytest xmlschema && python -m pytest schema ingest && node --test app/tests/*.test.js
```

Bez wcześniejszego `python -m ingest fetch-xsd` 2 testy XSD są pomijane – opis niżej w „Uruchomieniu”.

## Problem

Dane o defibrylatorach AED w Polsce są rozproszone i nikt nie odpowiada za ich aktualność. Na dane.gov.pl dane o AED publikują dziś tylko **3 gminy (50 urządzeń)**. Największy otwarty zbiór, OpenStreetMap (OpenAEDMap), ma ok. **18 300 AED**, ale to dane społeczne. Według statystyk z `ingest/` (22.11.2026):

- tylko 33% tych AED ma wskazanego dysponenta;
- tylko 17,6% sprawdzono w ostatnim roku;
- tylko 37% ma godziny dostępności;
- w 686 gminach są AED, ale przy żadnym nie wiadomo, kto za nie odpowiada.

Samo połączenie map w jedną tego nie naprawi, bo dane muszą mieć **właściciela**. To ustalenie z mentorami ([plan techniczny](docs/plan-techniczny.md), „Ustalenia z mentorami”).

## Rozwiązanie

Nie publikujemy danych sami. Dajemy dysponentom AED wszystko, czego potrzebują, żeby **opublikowali je na swoim koncie dane.gov.pl, w jednym formacie i pod własną odpowiedzialnością**.

1. **Wzorcowy zakres danych** (`schema/`): 41 pól na trzech poziomach (14 wymaganych, 20 zalecanych, 7 opcjonalnych; identyfikator nadaje system). Obejmuje lokalizację, dostępność (godziny w formacie `opening_hours`), stan techniczny, odpowiedzialność (dysponent, kto potwierdził lokalizację, kto odpowiada za stan techniczny) i pochodzenie danych.
   - Pliki: `aed.schema.json` (Frictionless Table Schema) i **arkusz XLSX do wypełnienia** z listami rozwijanymi, słownikiem pól i przykładem.
2. **Zestaw dla dostawcy** (`ingest/`): pobieranie i scalanie danych, walidacja ze schematem i **pakiet do publikacji** (`python -m ingest package`):
   - CSV i GeoJSON;
   - opis zbioru dla harwestera XML portalu, sprawdzony oryginalnym XSD portalu;
   - suma MD5;
   - raport braków;
   - instrukcja.

   Pakiet przyjmuje tylko licencje dopuszczone na portalu (CC), więc dane z OSM (ODbL) do niego nie trafiają.
3. **Wykaz zbiorczy AED w portalu** (`portal/`): zmiana w otwartym kodzie dane.gov.pl (2.63.0) na wzór Wykazu Głównego DGA. Instytucja zaznacza przy zasobie „Zawiera wykaz defibrylatorów AED” albo flaga przychodzi sama w pliku harwestera XML (schemat 1.14, `python -m ingest package … --wykaz-aed`), a portal codziennie o 4:00 skleja opublikowane zasoby z tą flagą, które przeszły walidację portalu, w jeden zasób CSV „Wykaz zbiorczy defibrylatorów AED”. AED różnych instytucji bliżej niż 50 m oznacza jako możliwy duplikat, zamiast je usuwać. W zasobach AED portal nie zgaduje typów kolumn tekstowych, więc np. kod TERYT czy REGON z samych cyfr z pustą komórką nie jest błędem walidacji. Sprawdzone na portalu uruchomionym lokalnie w dockerze ([`portal/README-AED.md`](portal/README-AED.md), uruchomienie: [`portal/README-DOCKER-AED.md`](portal/README-DOCKER-AED.md)).
4. **Weryfikacja przez dystrybutora** (`ingest/`): dla wybranego województwa lub gminy dystrybutor AED, np. Centrum Ratownictwa, dostaje listę urządzeń do sprawdzenia. Odhacza w niej „potwierdzam / inne miejsce / brak urządzenia”, a pipeline wczytuje wynik. Potwierdzone AED stają się zweryfikowane i mogą trafić do pakietu gminy.
5. **Mapa luk po gminach:** dla każdej z 2 479 gmin pokazuje, czy publikuje dane, ma tylko dane społeczne czy nie ma AED w danych. To lista adresatów akcji.
6. **Prototyp „Znajdź AED”** (`app/`): moduł w stylu dane.gov.pl, który pokazuje, po co są dobre dane. Zawiera:
   - mapę 18 tys. AED;
   - najbliższy AED „dostępny teraz”;
   - podpowiedzi z AED na mapie;
   - odległość pieszo i samochodem;
   - podstronę każdego AED;
   - wyraźne oznaczenie: **zweryfikowany** (instytucja odpowiada za dane) albo **niezweryfikowany** (dane społeczne).
7. **Akcja „AEDane”** (`branding/`): logotyp, księga znaku i hasło dla kampanii, która zachęca dysponentów do publikacji.

## Kroki użytkownika

- **Osoba szukająca AED:**
  1. Wybiera „Użyj mojej lokalizacji” albo wpisuje adres lub nazwę miejsca.
  2. Widzi najbliższy AED dostępny teraz i listę w promieniu 5 km z odległością pieszo i samochodem.
  3. Klika „Wyznacz trasę” (Mapy Google). W „Szczegółach” są godziny, dostęp, dysponent i źródło danych.
- **Dysponent (gmina, szpital, firma):** wypełnia arkusz XLSX albo przygotowuje CSV, uruchamia `python -m ingest package … --plik …` i publikuje pakiet na dane.gov.pl ręcznie albo przez harwester. Żeby zasób trafił do wykazu zbiorczego, przy publikacji ręcznej zaznacza przy nim „Zawiera wykaz defibrylatorów AED”, a przy harwesterze buduje pakiet z `--wykaz-aed` (plik XML w schemacie 1.14 z tą flagą – na portalu z naszą zmianą w `portal/`).
- **Dystrybutor AED:** dostaje listę do sprawdzenia (`python -m ingest dystrybutor …`), wypełnia ją w Excelu i oddaje. Wynik wczytuje `python -m ingest wczytaj-dystrybutora …`.

## Uruchomienie

Prototyp (bez budowania, dane są w repo):

```bash
cd app
npx --yes http-server -p 8000 -c-1               # albo: python -m http.server 8000
# → http://localhost:8000
```

Portal z wykazem zbiorczym AED (docker, ok. 20 GB wolnego dysku, min. 8 GB RAM): instrukcja krok po kroku w [`portal/README-DOCKER-AED.md`](portal/README-DOCKER-AED.md).

Dane i testy – z głównego katalogu repozytorium:

```bash
# Dane (Python 3.12)
python -m ingest fetch-gminy                     # jednorazowo: granice gmin z PRG (GUGiK)
python -m ingest fetch all && python -m ingest build all
python -m ingest stats                           # statystyki → ingest/data/out/statystyki.md
python app/scripts/build_data.py                 # dane dla prototypu

# Testy (wszystkie muszą przechodzić, 0 skipped)
pip install "frictionless>=5,<6" openpyxl pytest xmlschema
python -m ingest fetch-xsd                       # jednorazowo, ok. 90 MB: XSD harwestera portalu – bez niego 2 testy XSD są pomijane
python -m pytest schema ingest
node --test app/tests/*.test.js
```

Szczegóły są w README każdego katalogu.

## Struktura repozytorium

| Katalog | Zawartość | Właściciel |
|---|---|---|
| [`schema/`](schema/README.md) | wzorcowy zakres danych: schemat JSON, **arkusz XLSX**, przykład, testy | Krystian Poprawa |
| [`ingest/`](ingest/README.md) | pipeline danych, pakiet dla dostawcy, weryfikacja przez dystrybutora, mapa luk, statystyki | Mikołaj Rochowiak |
| [`app/`](app/README.md) | prototyp „Znajdź AED” (HTML/JS, WCAG 2.2 AA, wersja na telefon) | Krystian Poprawa |
| [`branding/`](branding/README.md) | logotyp „AEDane”, księga znaku, hasło | Krystian Poprawa |
| [`portal/`](portal/README-AED.md) | kod źródłowy portalu dane.gov.pl 2.63.0 (GPL v3) i nasze zmiany: wykaz zbiorczy AED | Mikołaj Rochowiak (środowisko docker: Tymoteusz Szymański) |
| `presentation/` | slajdy, zrzuty ekranu – **w przygotowaniu** | Krystian Poprawa |
| [`docs/`](docs/) | treść zadania, regulamin, plan techniczny, analiza portalu dane.gov.pl, rejestr użycia AI | wspólny |

Zasady pracy zespołu i agentów AI: [AGENTS.md](AGENTS.md).

## Checklista oddania (z treści zadania)

- [x] Szczegółowy opis i tytuł projektu – ten plik
- [ ] Prezentacja: min. 5 slajdów ze zrzutami ekranu, opis funkcjonalności i kroków użytkownika, lista ograniczeń
- [x] Prototyp rozwiązania – [`app/`](app/README.md) (moduł „Znajdź AED”) i [`portal/`](portal/README-AED.md) (wykaz zbiorczy AED w kodzie portalu)
- [x] Wzorcowy zakres danych o AED (tabela .xlsx) – [`schema/wzorcowy-zakres-danych-aed.xlsx`](schema/wzorcowy-zakres-danych-aed.xlsx)
- [x] Kod źródłowy – to repozytorium
- [x] Logotyp (.jpg, .png, .pdf + format otwarty .svg) i księga znaku (.pdf) – [`branding/`](branding/README.md)
- [ ] Opis zakresu wykorzystania AI (wymóg regulaminu, §2 pkt 8) – [`docs/ai-usage.md`](docs/ai-usage.md), do uzupełnienia przez wszystkich na hasło „zbieramy rejestr AI”

## Ograniczenia

- Prototyp korzysta z publicznych usług:
  - trasy: serwery FOSSGIS;
  - wyszukiwanie adresu: Nominatim i GUGiK;
  - podkład mapy: OpenStreetMap;
  - zdjęcia: OpenAEDMap.

  Przy wdrożeniu na dane.gov.pl potrzebne byłyby własny serwer tras i miniatury zdjęć.
- 99,7% AED w prototypie to dane społeczne (OSM), oznaczone jako niezweryfikowane. Zweryfikowanych jest 49, bo tyle dziś publikują instytucje (z 50 punktów gmin jeden – ze zbioru Marek – leży w Krośnie, więc nie liczy się jako zweryfikowany), i właśnie to ma zmienić akcja.
- Godziny dostępności są w danych tylko przy 37% AED. Gdy ich nie ma, strona nie obiecuje dostępności.
- Wykaz zbiorczy AED działa na portalu uruchomionym lokalnie (docker). Na dane.gov.pl musiałoby go wdrożyć Ministerstwo Cyfryzacji.
- Flaga „Zawiera wykaz defibrylatorów AED” w pliku harwestera wymaga schematu 1.14 z naszej zmiany w `portal/` (`python -m ingest package … --wykaz-aed`, opis w [`portal/README-AED.md`](portal/README-AED.md)). Dzisiejszy dane.gov.pl zna tylko schemat 1.13 – tam flagę trzeba zaznaczyć ręcznie w panelu. W API portalu flagi jeszcze nie ma.
- Na portalu lokalnym import przez harwester XML z kodem gminy TERYT wymaga usługi geokodowania portalu (Pelias), której nie ma w docker compose (na dane.gov.pl – według kodu – działa produkcyjny geokoder portalu; tego nie testowaliśmy). Demo `portal/aed_demo.sh` jej nie potrzebuje, a obejście do testu harwestera opisuje [`docs/panel-administracyjny.md`](docs/panel-administracyjny.md) (krok 2a).
- Szczegółowe ograniczenia: [`app/README.md`](app/README.md), [`ingest/README.md`](ingest/README.md), [`portal/README-AED.md`](portal/README-AED.md), [`docs/panel-administracyjny.md`](docs/panel-administracyjny.md).

## Licencje i prawa

- **Kod i dokumenty zespołu** (`schema/`, `ingest/`, `app/` bez `app/vendor/` i `app/data/`, `branding/`, `presentation/`, `docs/` bez treści zadania i regulaminu): autorstwa zespołu. Prawa majątkowe zwycięskiego rozwiązania przechodzą na Ministerstwo Cyfryzacji zgodnie z §4 regulaminu. Pliki PNG logotypu i sygnetu wygenerowano w Gemini 4 Hydrogen na polecenie zespołu; pozostałe formaty i księgę znaku przygotował zespół (zakres użycia AI – `docs/ai-usage.md`).
- **Elementy zewnętrzne zostają na swoich licencjach i nie są przedmiotem przeniesienia praw:**
  - treść zadania i regulamin (`docs/zadanie-misja-aed.*`, `docs/regulamin-misja-aed.*`) – dokumenty organizatora;
  - Leaflet (BSD-2), Leaflet.markercluster (MIT), krój Roboto (SIL OFL) – licencje w `app/vendor/`;
  - krój Montserrat (SIL OFL) – użyty w księdze znaku `branding/`;
  - dane OpenStreetMap / OpenAEDMap w `app/data/` – **ODbL 1.0**, © autorzy OpenStreetMap, atrybucja jest na stronie;
  - zdjęcia miejsc wczytywane z OpenAEDMap – CC0;
  - dane gmin z dane.gov.pl – licencje zbiorów (CC0, CC BY 4.0), atrybucja jest na stronie.
- **Kod portalu dane.gov.pl** w `portal/` (GPL v3): pierwszy commit to oryginał 2.63.0, a nasze zmiany w nim też są na GPL v3 ([`portal/README-AED.md`](portal/README-AED.md)). XSD harwestera jest w `portal/data/harvester/`; `ingest` korzysta z własnej kopii pobieranej przez `fetch-xsd`.
- **Wygląd modułu `app/`** odtwarza układ dane.gov.pl (kolory, wymiary, treść linków), ale nie zawiera skopiowanych plików portalu (kod portalu jest na GPL v3). Gdyby zespół zdecydował się takie pliki dodać, `app/` trzeba by udostępnić na GPL v3 – szczegóły w [`app/README.md`](app/README.md).
