# app/ – prototyp „Znajdź AED”

Obszar Krystiana (patrz `AGENTS.md`). Statyczna strona: przycisk **Znajdź AED** odczytuje lokalizację, pod spodem pokazuje mapę ze wszystkimi AED i wyróżnia najbliższy **dostępny teraz**. „Wyznacz trasę pieszo” otwiera Mapy Google (na telefonie – aplikację). Wygląd i układ odtworzone wg kodu frontendu dane.gov.pl (pasek górny, przełączniki kontrastu A/A/A/A i wielkości tekstu A–A+++, menu z podkreśleniem, okruszki „Jesteś w sekcji”, panel „Filtry”, karty wyników, granatowa stopka; paleta i Roboto). Kod napisany od nowa – nie kopiujemy plików portalu (GPL v3). **Bez znaków państwowych:** zamiast godła, „gov.pl”, „Serwis Rzeczypospolitej Polskiej”, logo Otwarte Dane i UE – znak i opis prototypu (strona nie może udawać serwisu państwowego; po przyjęciu przez MC podmiana to kilka linii w `index.html`).

## Uruchomienie

Bez instalacji i bez budowania:

```bash
cd app && python -m http.server 8000   # potem http://localhost:8000
```

Bez Pythona (Windows): `npx --yes http-server -p 8000` (wymaga Node.js) albo dwuklik w `index.html` – wtedy zamiast lokalizacji wybierz miejscowość z listy.

Lokalizacja działa tylko w bezpiecznym kontekście (`https://` albo `http://localhost`). Po otwarciu `index.html` prosto z dysku strona działa, ale przeglądarka może odmówić lokalizacji – wtedy wybierz miejscowość z listy albo kliknij na mapie.

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
