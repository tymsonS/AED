# presentation/ – prezentacja projektu AEDane

Właściciel: Krystian Poprawa (`AGENTS.md`).

Wymóg formalny (`docs/zadanie-misja-aed.md`, pkt 4): prezentacja z **co najmniej 5 slajdami ze zrzutami ekranu** jako dowodem spełnienia wymagań technicznych, **opisem funkcjonalności z krokami użytkownika** i **listą ograniczeń**.

## Gdzie jest prezentacja

- **Wersja robocza (do edycji):** deck „AEDane – Misja AED (prezentacja, 10 slajdów)” w Claude Slides, prywatny link Krystiana – udostępnia zespołowi Krystian.
- **Wersja do oddania:** `aedane-prezentacja.pdf` w tym katalogu – eksport z Claude Slides (Udostępnij › Eksport › PDF). **Jeszcze jej nie ma** – trafi tu po akceptacji zespołu.

Hasło prezentacji: **„Otwarte dane. Cenne sekundy. Uratowane życie.”**

## Struktura (10 slajdów)

| # | Slajd | Co pokazuje | Zrzut / materiał |
|---|---|---|---|
| 1 | Tytułowy | logotyp, hasło, zespół; telefon z mapą i najbliższym AED wzorcowym (zweryfikowany, czynny całą dobę) | `branding/logotyp-aedane.svg`, `zrzuty/obywatel-2-wynik.jpg` |
| 2 | Problem i wyzwanie | historia z treści zadania; 50 AED na dane.gov.pl (3 z 2 479 gmin) vs ok. 18,3 tys. w OSM; wyzwanie | `zrzuty/mapa-luk.jpg` |
| 3 | Nasza odpowiedź: AEDane | 4 kroki prostym językiem: wspólny formularz → sprawdzenie i paczka → jeden wykaz na dane.gov.pl → Znajdź AED; akcja AEDane | sygnet |
| 4 | Wzorcowy zakres danych | 41 pól (14/20/7), 8 grup; **wzorcowo opisany AED**: zweryfikowany, ze zdjęciem, godzinami, dostępem, opisem miejsca, dysponentem | `zrzuty/rekord-wzorcowy.jpg` |
| 5 | Architektura i zgodność z dane.gov.pl | dla osób spoza IT: 3 kroki (instytucja wgrywa plik → portal łączy co noc → każdy korzysta), wynik 50 AED z portalu, zasady portalu | – (wynik: `zrzuty/portal-demo-wykaz.png`) |
| 6 | Ścieżka: dysponent danych | 5 kroków instytucji + 3 kroki dystrybutora | – |
| 7 | Ścieżka: obywatel i ratownik | 4 kroki od telefonu do czynnego AED, na AED wzorcowym | `zrzuty/obywatel-1…4-*.jpg` |
| 8 | Dostępność WCAG i testy | axe-core (14 widoków, 0 naruszeń poza opisanym wyjątkiem 2.5.8), 328 testów, tryb kontrastu, tekst 200% (A+++), pomoc przy lokalizacji | `zrzuty/wcag-*.jpg` |
| 9 | Ograniczenia i dalszy rozwój | **lista ograniczeń** i propozycje rozwoju | – |
| 10 | Dziękujemy za uwagę | hasło, logotyp, zespół, repozytorium | – |

Zrzuty ekranu są na slajdach 1, 2, 4, 7 i 8 (wymóg: min. 5). Kroki użytkownika: slajdy 6 i 7. Ograniczenia: slajd 9.

## Skąd są liczby i zrzuty

- **Statystyki** (slajdy 2, 9): `python -m ingest stats` i `python -m ingest gaps` z 22.11.2026. Prototyp pokazuje 18 306 AED (dane z 21.11.2026), stąd „ok. 18,3 tys.”.
- **Rekord wzorcowy** (slajdy 1, 4 i 7): rekord przykładowy z arkusza „Przykład” w `schema/wzorcowy-zakres-danych-aed.xlsx` (Centrum Kultury Przykładowe – **dane poglądowe**, opisane tak na slajdzie), dopisany tylko do **kopii** danych prototypu przez `narzedzia/rekord_wzorcowy.js`. Zdjęcie poglądowe: OpenAEDMap, CC0. W prawdziwych danych nie ma dziś AED, który byłby jednocześnie zweryfikowany i miał zdjęcie – 49 zweryfikowanych AED gmin nie ma zdjęć ani godzin.
- **Zrzuty prototypu:** `narzedzia/zrzuty.py` (Playwright, Chromium) na kopii prototypu z gałęzi `krystian/app-kontrast-poprawki` (poprawki kolorów w trybach kontrastu) z dopisanym AED wzorcowym; zegar ustawiony na wtorek 11:00, położenie przy AED wzorcowym (Warszawa). Telefon: iPhone, 390×844 px; tekst 200%: 768×1024 px (opcja A+++ jest od 768 px, jak na dane.gov.pl). Krój pisma prezentacji: Inter (pełne polskie znaki).
- **Portal:** wynik `portal/aed_demo.sh` z `portal/README-DOCKER-AED.md` (22.11.2026, prawdziwe dane 3 gmin → wykaz 50 AED).
- **Testy** (slajd 8): `node --test app/tests/*.test.js` – 63; `pytest schema ingest` – 251 (z XSD, 0 pominiętych); testy scalania wykazu w portalu – 14 (`portal/mcod/resources/tests/test_aed_merge.py`, uruchamiane w kontenerze portalu).
- **Mapa luk:** `narzedzia/mapa_luk.py` z `ingest/data/out/mapa-luk.geojson`.

## Do zrobienia przed oddaniem

- [ ] akceptacja treści przez zespół;
- [ ] scalenie poprawek kontrastu (`krystian/app-kontrast-poprawki`), żeby prototyp wyglądał jak na slajdzie 8;
- [ ] eksport PDF do `presentation/aedane-prezentacja.pdf`.
