# presentation/ – prezentacja projektu AEDane

Wymóg formalny (`docs/zadanie-misja-aed.md`, pkt 4): prezentacja z **co najmniej 5 slajdami ze zrzutami ekranu** jako dowodem spełnienia wymagań technicznych, **opisem funkcjonalności z krokami użytkownika** i **listą ograniczeń**.

## Gdzie jest prezentacja

- **`aedane-prezentacja.pptx`** – wersja do edycji (PowerPoint).
- **`aedane-prezentacja.pdf`** – wersja do oddania, wygenerowana z pliku .pptx (LibreOffice, 10 stron, 16:9).
- **`wideo-prezentacja-aedane.mp4`** – film z prototypu „Znajdź AED” (68 s, 1920×1080, bez dźwięku): ścieżka obywatela na telefonie, wzorcowo opisany AED, legenda, tryb wysokiego kontrastu. Na YouTube: <https://youtu.be/jwqozqicyYk>. Opis scen i ponowne nagranie: [`narzedzia/wideo/`](narzedzia/wideo/README.md).

Hasło prezentacji: **„Otwarte dane. Cenne sekundy. Uratowane życie.”**

## Struktura (10 slajdów)

| # | Slajd | Co pokazuje | Zrzut / materiał |
|---|---|---|---|
| 1 | Tytułowy | logotyp, hasło, zespół; telefon z mapą i najbliższym AED wzorcowym (zweryfikowany, czynny całą dobę) | `branding/logotyp-aedane.svg`, `zrzuty/obywatel-2-wynik.jpg` |
| 2 | Problem i wyzwanie | historia z treści zadania; 50 AED na dane.gov.pl (3 z 2 479 gmin) vs ok. 18,3 tys. w OSM; wyzwanie | `zrzuty/mapa-luk.jpg` |
| 3 | Nasza odpowiedź: AEDane | 4 kroki prostym językiem: wspólny formularz → sprawdzenie i paczka → jeden wykaz na dane.gov.pl → Znajdź AED; akcja AEDane | sygnet |
| 4 | Wzorcowy zakres danych | 41 pól (14/20/7), 8 grup; **wzorcowo opisany AED**: góra strony (status, adres, zdjęcie, mapa) i dane pod mapą (dostępność, miejsce, dysponent, weryfikacja) | `zrzuty/rekord-wzorcowy.jpg`, `zrzuty/rekord-wzorcowy-dane.jpg` |
| 5 | Architektura i zgodność z dane.gov.pl | dla osób spoza IT: 3 kroki (instytucja wgrywa plik → portal łączy wszystko → każdy korzysta), 4 powody zgodności z zasadami portalu | – (wynik: `zrzuty/portal-demo-wykaz.png`) |
| 6 | Ścieżka: dysponent danych | 5 kroków instytucji + 3 kroki dystrybutora | – |
| 7 | Ścieżka: obywatel i ratownik | 4 kroki: 112 i lokalizacja → najbliższy czynny AED → dymek → trasa w Mapach Google | `zrzuty/obywatel-1…4-*.jpg` |
| 8 | Dostępność WCAG i testy | tryb kontrastu, tekst 200% (A+++), pomoc przy lokalizacji; 4 tryby kontrastu, brak przewijania w poziomie od 320 px, klawiatura i czytnik ekranu, wyjątek 2.5.8 dla gęstych pinezek | `zrzuty/wcag-*.jpg` |
| 9 | Ograniczenia | **lista ograniczeń**: dane społeczne, godziny dostępności, wdrożenie wykazu przez MC, flaga AED (schemat harwestera 1.14 vs 1.13), publiczne usługi | – |
| 10 | Dziękujemy za uwagę | hasło, logotyp, zespół, repozytorium | – |

Zrzuty ekranu są na slajdach 1, 2, 4, 7 i 8 (wymóg: min. 5). Kroki użytkownika: slajdy 6 i 7. Ograniczenia: slajd 9.

## Skąd są liczby i zrzuty

- **Statystyki** (slajdy 2, 9): `python -m ingest stats` i `python -m ingest gaps` (stan danych z 22.11.2026). Prototyp pokazuje 18 317 AED, stąd „ok. 18,3 tys.”.
- **Rekord wzorcowy** (slajdy 1, 4 i 7): rekord przykładowy z arkusza „Przykład” w `schema/wzorcowy-zakres-danych-aed.xlsx` (Centrum Kultury Przykładowe – **dane poglądowe**, opisane tak na slajdzie; na potrzeby zrzutów położony przy Al. Lotników 16 w Warszawie, gdzie w pobliżu nie ma innego AED), dopisany tylko do **kopii** danych prototypu przez `narzedzia/rekord_wzorcowy.js`. Zdjęcie poglądowe: OpenAEDMap, CC0. W prawdziwych danych nie ma dziś AED, który byłby jednocześnie zweryfikowany i miał zdjęcie – 49 zweryfikowanych AED gmin nie ma zdjęć ani godzin.
- **Zrzuty prototypu:** `narzedzia/zrzuty.py` (Playwright, Chromium) na kopii prototypu z dopisanym AED wzorcowym. Zegar: wtorek 11:00. Start: 52.176, 21.016 – ok. 220 m od AED wzorcowego, więc odległości są realne (220 m w linii prostej, 280 m pieszo, 270 m samochodem z serwerów tras). Telefon: iPhone, 390×844 px; tekst 200%: 768×1024 px (opcja A+++ jest od 768 px, jak na dane.gov.pl). Krok 4 slajdu 7 to zrzut Map Google otwartych przyciskiem „Wyznacz trasę” z tego samego punktu. Krój pisma prezentacji: Arial (pełne polskie znaki).
- **Portal:** wynik `portal/aed_demo.sh` z `portal/README-DOCKER-AED.md` (prawdziwe dane 3 gmin → wykaz 50 AED).
- **Testy** (wymienione w `README.md`, nie na slajdach): `node --test app/tests/*.test.js` – 63; `pytest schema ingest` – 256 (z XSD portalu, 0 pominiętych); w portalu – testy scalania wykazu (`portal/mcod/resources/tests/test_aed_merge.py`) i harwestera (`portal/mcod/harvester/tests`), uruchamiane w kontenerze `mcod-local-tests`.
- **Mapa luk:** `narzedzia/mapa_luk.py` z `ingest/data/out/mapa-luk.geojson`.

