# presentation/ – prezentacja projektu AEDane

Właściciel: Krystian Poprawa (`AGENTS.md`).

Wymóg formalny (`docs/zadanie-misja-aed.md`, pkt 4): prezentacja z **co najmniej 5 slajdami ze zrzutami ekranu** jako dowodem spełnienia wymagań technicznych, **opisem funkcjonalności z krokami użytkownika** i **listą ograniczeń**.

## Gdzie jest prezentacja

- **Wersja robocza (do edycji):** deck w Claude Slides, prywatny link Krystiana – udostępnia zespołowi Krystian.
- **Wersja do oddania:** `aedane-prezentacja.pdf` w tym katalogu – eksport z Claude Slides (Udostępnij › Eksport › PDF). **Jeszcze jej nie ma** – trafi tu po akceptacji zespołu.

## Struktura (21 slajdów)

Kolejność idzie za kryteriami oceny: najpierw problem, potem rozwiązanie z największymi wagami (zgodność z dane.gov.pl 30%, logo i hasło 25%), na końcu wymagania formalne.

| # | Slajd | Po co | Zrzut / materiał |
|---|---|---|---|
| | **1. Problem** | | |
| 1 | Okładka: logotyp, hasło „AEDane ratują życie.”, zespół | pierwsze wrażenie, nazwa akcji | `branding/logotyp-aedane.png` |
| 2 | Za dane o AED nikt dziś nie odpowiada | 50 AED na dane.gov.pl vs 18 317 w OSM; 32,9% / 17,6% / 37,1% | `ingest stats` |
| 3 | Mapa luk: dane publikują 3 z 2 479 gmin | 2 128 gmin z AED w danych, 686 bez dysponenta, 351 bez AED | `zrzuty/mapa-luk.jpg` |
| | **2. Rozwiązanie** | | |
| 4 | Dane muszą mieć właściciela | teza projektu (ustalenie z mentorami) | – |
| 5 | Sześć części, jeden obieg danych | mapa całego rozwiązania: schema → ingest → portal → app + weryfikacja, akcja | – |
| 6 | Wzorcowy zakres danych: 41 pól (14/20/7) | kryterium 10% | `zrzuty/xlsx-slownik.png` |
| 7 | Pakiet gotowy do publikacji na dane.gov.pl | kryterium 30%: CSV, GeoJSON, XML harwestera z XSD, MD5, licencje CC | `zrzuty/pakiet-dostawcy.png` |
| 8 | Portal scala wykazy wszystkich dysponentów | kryterium 30%: wykaz zbiorczy wzorem DGA (PR #58) | `zrzuty/portal-wykaz-aed.png` |
| 9 | Każdy AED mówi, kto odpowiada za jego dane | poziomy zaufania 1–3, weryfikacja przez dystrybutora | – |
| | **3. Prototyp „Znajdź AED”** | | |
| 10 | Trzy kroki do najbliższego defibrylatora | **kroki użytkownika** na telefonie | `zrzuty/mobile-podpowiedzi.jpg`, `mobile-wynik.jpg`, `mobile-dymek.jpg` |
| 11 | Od razu widać, kto odpowiada za dane AED | zweryfikowany / niezweryfikowany, „dostępny teraz”, trasy | `zrzuty/desktop-zweryfikowany.jpg` |
| 12 | Strona AED: wszystko, co trzeba wiedzieć | podstrona, źródło, prywatność | `zrzuty/szczegoly-desktop.jpg` |
| 13 | Dostępność (WCAG 2.2 AA) i wersja na telefon | kontrast, 320 px, klawiatura, fokus | `zrzuty/mobile-kontrast.jpg`, `ekran-320px.jpg`, `mobile-pomoc-lokalizacja.jpg` |
| 14 | Trzy role, trzy ścieżki | **kroki użytkownika**: osoba szukająca, dysponent, dystrybutor | – |
| | **4. Akcja AEDane** | | |
| 15 | Logo i hasło, koncepcja („A dane?”) | kryterium 25% | `branding/` |
| 16 | Księga znaku: wersje, pole ochronne, zakazy, kolory | wymóg formalny | strony 3, 5, 6 księgi |
| 17 | Akcja trafia do konkretnych adresatów | mapa luk jako lista adresatów, zastosowania z księgi | – |
| | **5. Zamknięcie** | | |
| 18 | Ograniczenia | **lista ograniczeń** (wymóg) | – |
| 19 | Wymagania zadania – gdzie je spełniamy | tabela dla jury: wymaganie → plik → slajd | – |
| 20 | Jakość i użycie AI | testy (248 + 63, 0 pominiętych), regulamin §2 pkt 7–8 | `zrzuty/testy.png` |
| 21 | „A dane?” – repozytorium, prototyp, zespół | zakończenie | – |

Zrzuty ze slajdów 2–13 i 20 spełniają wymóg „min. 5 slajdów ze zrzutami ekranu”.

## Skąd są liczby i zrzuty

- **Statystyki** (slajdy 2, 3, 17): `python -m ingest stats` i `python -m ingest gaps` z 22.11.2026 na `main` (d77ded0). Prototyp pokazuje 18 306 AED, bo jego dane zbudowano 21.11.2026.
- **Zrzuty prototypu:** `narzedzia/zrzuty.py` (Playwright, Chromium), gałąź `krystian/app-fokus-dymku` (PR #59), zegar ustawiony na wtorek 11:00, położenie: Kraków, Rynek i Krosno. Telefon: 390×844 px, iPhone.
- **Mapa luk:** `narzedzia/mapa_luk.py` z `ingest/data/out/mapa-luk.geojson`.
- **Pakiet i XML:** prawdziwy przebieg `python -m ingest package danegovpl-krosno …` (walidacja: 0 błędów, `aed.xml` zgodny z XSD harwestera 1.13).
- **Kod portalu:** fragment różnicy z PR #58 (gałąź `mikolaj/portal-wykaz-aed`).
- **Arkusz XLSX:** `schema/wzorcowy-zakres-danych-aed.xlsx` wyrenderowany przez LibreOffice. Zrzut z Excela można podmienić.

## Do uzupełnienia przed oddaniem

- [ ] imiona i nazwiska zespołu (slajdy 1 i 21);
- [ ] link do repozytorium i adres prototypu (slajdy 19 i 21);
- [ ] status PR #58 (slajd 8);
- [ ] eksport PDF do `presentation/aedane-prezentacja.pdf`.
