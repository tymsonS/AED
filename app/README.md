# app/ – prototyp „Znajdź AED”

Obszar Krystiana (patrz `AGENTS.md`). Statyczna strona: przycisk **Znajdź AED** odczytuje lokalizację, pod spodem pokazuje mapę ze wszystkimi AED i wyróżnia najbliższy **dostępny teraz**. „Wyznacz trasę pieszo” otwiera Mapy Google (na telefonie – aplikację). Wygląd i układ odtworzone wg kodu frontendu dane.gov.pl: pasek górny, przełączniki kontrastu A/A/A/A i wielkości tekstu A–A+++, PL/EN, Zarejestruj się / Zaloguj się, pełne menu portalu (z „Więcej”), okruszki „Jesteś w sekcji”, panel „Filtry”, karty wyników, czterokolumnowa stopka z CMS portalu. Linki menu i stopki prowadzą do prawdziwych podstron dane.gov.pl – strona działa jak dodatkowa podstrona portalu. Mapa ze wszystkimi AED jest widoczna od wejścia na stronę.

**Bez znaków państwowych:** zamiast godła, „gov.pl”, „Serwis Rzeczypospolitej Polskiej”, logo Otwarte Dane, logo UE i „Mój Gov” – znak i opis modułu (strona hostowana poza portalem nie może udawać serwisu państwowego). Po wpięciu w dane.gov.pl moduł dostaje nagłówek portalu; podmiana to kilka linii w `index.html`.

**Licencja:** kod portalu jest na GPL v3. Krystian dopuścił kopiowanie jego plików; jeśli to zrobimy, `app/` musi być udostępniony na GPL v3 (decyzja zespołu, także w kontekście przeniesienia praw na MC z regulaminu). Obecna wersja nie zawiera skopiowanych plików portalu – tylko odtworzone wartości (kolory, wymiary) i treść linków.

## Uruchomienie

Bez instalacji i bez budowania:

```bash
cd app && python -m http.server 8000   # potem http://localhost:8000
```

Bez Pythona (Windows): `npx --yes http-server -p 8000 -c-1` (wymaga Node.js; `-c-1` wyłącza pamięć podręczną) albo dwuklik w `index.html` – wtedy zamiast lokalizacji wybierz miejscowość z listy.

Lokalizacja działa tylko w bezpiecznym kontekście (`https://` albo `http://localhost`). Po otwarciu `index.html` prosto z dysku strona działa, ale przeglądarka może odmówić lokalizacji – wtedy wybierz miejscowość z listy albo kliknij na mapie.

Pliki CSS/JS są dołączane z numerem wersji (`?v=…` w `index.html`) – po każdej zmianie stylów lub skryptów podbij go, żeby przeglądarki nie użyły starych plików z pamięci podręcznej.

Podkład mapy pobierany jest z serwerów OpenStreetMap, więc mapa wymaga internetu. Leaflet i czcionka Roboto są w `vendor/` (bez CDN).

## Dane

`data/aed-data.js` generuje `scripts/build_data.py` z wyniku pipeline'u `ingest/` i z przykładu w `schema/`:

```bash
python -m ingest fetch all && python -m ingest build all
python app/scripts/build_data.py
```

- **50 AED** z dane.gov.pl (Przemyśl, Krosno, Marki) – stan `main` z 21.11.2026.
- **Rekordy przykładowe** z `schema/przyklad-aed.csv` (3, fikcyjne) – domyślnie ukryte, włączane w filtrach, oznaczone na liście i mapie; bez klikalnego telefonu. Służą do pokazania logiki „dostępny teraz”.
- Żaden z 50 prawdziwych rekordów nie ma dziś godzin dostępności, więc strona uczciwie pokazuje „godziny nieznane” i wyróżnia najbliższy AED z takim zastrzeżeniem.

## Jak liczymy „dostępny teraz”

`js/aed-core.js` (bez zależności, testowany w Node):
- `status` = `nieaktywny` / `w_serwisie` albo `dostep` = `prywatny` → niedostępny,
- `godziny_dostepnosci` w składni OSM `opening_hours` – obsługiwany podzbiór: `24/7`, dni (`Mo-Fr`, `Sa,Su`, `Fr-Mo`), przedziały (`08:00-16:00`, kilka po przecinku, przez północ), `off`; późniejsza reguła nadpisuje wcześniejszą,
- **wszystko, czego parser nie rozumie (np. `PH off`, `sunrise-sunset`), daje „godziny nieznane” – nigdy „dostępny”.**

## Testy

```bash
node --test app/tests/*.test.js
```

Logika godzin i odległości, kontrola wygenerowanych danych, kontrast kolorów (WCAG 2.2 AA: tekst ≥ 4,5:1, grafika ≥ 3:1). Wszystkie muszą przechodzić.

## Dostępność (WCAG 2.2 AA)

Język `pl`, link „Przejdź do wyników”, widoczny fokus, cele ≥ 24 px (przyciski ≥ 44 px), komunikaty w `role="status"`, lista jako pełny odpowiednik mapy, informacja nie tylko kolorem (etykiety tekstowe), `prefers-reduced-motion`, układ mobile first.

## Licencje komponentów

Leaflet 1.9.4 – BSD-2-Clause (`vendor/leaflet/LICENSE`), Roboto – SIL OFL 1.1 (`vendor/roboto/LICENSE`), podkład © autorzy OpenStreetMap (ODbL). Atrybucja zbiorów z dane.gov.pl (CC0 / CC BY 4.0) w stopce strony.
