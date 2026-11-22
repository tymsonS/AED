# portal/ – kod źródłowy portalu dane.gov.pl w projekcie AEDane

Obszar `portal/` (właściciel w `AGENTS.md`). Oryginalny `README.md` w tym katalogu to dokumentacja portalu (konfiguracja środowiska, docker compose). Ten plik opisuje, skąd jest kod i co w nim zmieniamy.

## Skąd jest kod

- **Źródło:** https://dane.gov.pl/source-code/backend_latest.zip, czyli backend portalu (projekt `mcod`, Django).
- **Wersja:** 2.63.0 z 28.10.2026 (`CHANGELOG.md`), archiwum z 09.11.2026, SHA-256 `85949002eaa9f96c4dc2207c9a62caa29e5eae55d5ea5e9bd78a179ce0c3f47a`.
- **Licencja:** GPL v3. Nasze zmiany w tym katalogu też są na GPL v3.
- **Pierwszy commit `portal/` to oryginał bez zmian.** Tak radził mentor („rozpakowany kod źródłowy jako pierwszy commit, a następnie własny przyrost w kolejnych commitach”), więc nasze zmiany widać w historii gita jako różnicę względem oryginału.
- **Pominięte** tylko duże artefakty binarne, które są w oryginalnym archiwum:
  - `statics/` – zbudowany frontend, 78 MB;
  - `docker/rdfdb/fuseki/dist/` – paczka Apache Jena Fuseki, 51 MB.

  Do pełnego środowiska dockera trzeba je skopiować z archiwum albo uruchomić portal z archiwum, jak robi to Tymek.

## Po co

Mentor (Discord, 21.11.2026): najważniejsze jest **dostosowanie i przebudowanie logiki i metod w portalu**, żeby „wykazy” zasobów wielu dostawców dało się pobierać i scalać w jedną standardową listę. Wzorem jest **Wykaz Główny DGA**: instytucje publikują zasoby z flagą, a portal codziennie skleja je w jeden zasób zbiorczy. Analiza z odwołaniami do kodu: [`docs/analiza-wykazow-portalu.md`](../docs/analiza-wykazow-portalu.md).

## Nasze zmiany

### Wykaz zbiorczy AED (zrobione, do sprawdzenia na działającym portalu)

Na wzorze Wykazu Głównego DGA, w osobnych plikach, żeby różnica względem oryginału była czytelna:

| Plik | Co robi | Odpowiednik DGA |
|---|---|---|
| `mcod/resources/models.py` | flaga zasobu **`contains_aed_data`** („Zawiera wykaz defibrylatorów AED”) i singleton **`AggregatedAEDInfo`** | `contains_protected_data`, `AggregatedDGAInfo` |
| `mcod/resources/migrations/0076_aedane_wykaz_aed.py` | migracja obu zmian | – |
| `mcod/resources/aed_merge.py` | **scalanie bez Django**: kolumny wzorcowego zakresu AED v0.2 (41 pól); pomijanie pojedynczych błędnych wierszy z powodem (współrzędne, Polska, nazwa); `id_aed` nadawane przez system, gdy puste – z identyfikatora instytucji (stałe po ponownym wgraniu pliku), dwa AED w tym samym miejscu bez `id_zrodlowe` dostają dopisek -2 jak w `ingest/`; **scalanie po `id_aed`** (nowsza `data_weryfikacji`, przy remisie potwierdzona lokalizacja); **AED innych instytucji bliżej niż 50 m oznaczane w kolumnie `mozliwy_duplikat`** zamiast usuwania | `create_main_dga_df` (tylko `pd.concat`) |
| `mcod/resources/aed_utils.py` | wybór zasobów z flagą i udaną walidacją, odczyt `tabular_data`, plik CSV, zasób i zbiór „Wykaz zbiorczy defibrylatorów AED” właściciela z ustawień, podmiana poprzedniego (pusty wynik nie zastępuje poprzedniego wykazu), sprzątanie | `dga_utils.py` |
| `mcod/resources/tasks/aed.py` | zadanie Celery `create_main_aed_resource_task` | `tasks/dga.py` |
| `mcod/celeryapp.py` | harmonogram: codziennie o 4:00 (po DGA o 3:30) | `dga_main_resource_creation` |
| `mcod/settings/base.py` | `MAIN_AED_*`: właściciel zbioru (`MAIN_AED_DATASET_OWNER_ORGANIZATION_PK`), tytuły, opis, kategoria `HEAL` | `MAIN_DGA_*` |
| `mcod/resources/admin.py` | pole flagi w formularzu zasobu w panelu | pole `contains_protected_data` |
| `mcod/resources/tests/test_aed_merge.py` | 8 testów scalania (bez bazy danych) | – |

Wynik: kolumny wzorcowego zakresu AED i do tego `instytucja_publikujaca`, `id_zasobu_zrodlowego`, `mozliwy_duplikat` (odpowiednik „Nazwa dysponenta zasobu” w DGA).

**Sprawdzone bez portalu:**
- testy `test_aed_merge.py`: 8/8;
- scalenie prawdziwych zbiorów trzech gmin z dane.gov.pl (Krosno 21, Przemyśl 21, Marki 8) jako trzech zasobów: **50 AED w wykazie**, a jako możliwy duplikat oznaczony AED z Marek ze współrzędnymi pływalni w Krośnie (znany błąd w danych Marek);
- kompilacja wszystkich zmienionych plików.

**Do sprawdzenia na portalu (Tymek):** migracja, pole w panelu, uruchomienie zadania (`docs/panel-administracyjny.md`).

### Jak uruchomić (na postawionym portalu)

1. `python manage.py migrate resources` (migracja `0076_aedane_wykaz_aed`).
2. Zmienna środowiskowa **`MAIN_AED_DATASET_OWNER_ORGANIZATION_PK`**: pk instytucji-właściciela wykazu. Lokalnie np. `2838` („Pierwsza instytucja” z danych startowych), bo domyślne `333` lokalnie nie istnieje. Kategoria o kodzie `HEAL` musi istnieć (dane startowe mają tylko `AGRI`).
3. W panelu zasoby AED gmin, np. `aed.csv` z pakietu dostawcy z `ingest/`, oznaczyć **„Zawiera wykaz defibrylatorów AED”** i poczekać na udaną walidację zasobu.
4. Uruchomić zadanie bez czekania na 4:00:
   ```bash
   docker compose -f docker-compose.local.yml run mcod-local-run python manage.py shell -c      "from mcod.resources.tasks.aed import create_main_aed_resource_task as t; t.apply()"
   ```
5. Wynik: zbiór **„Wykaz zbiorczy defibrylatorów AED”** z zasobem CSV.

### Dalej
- element `containsAedData` w XSD harwestera (nowa wersja schematu), żeby flaga przychodziła automatycznie z pakietem dostawcy z `ingest/`;
- walidacja pliku przy zaznaczeniu flagi w formularzu (wymagane kolumny), jak `_validate_dga_file`;
- flaga w API i serializerach zasobu.

Panel administracyjny i harwester (dodawanie zasobów, automatyczne zasilanie pakietem dostawcy z `ingest/`): [`docs/panel-administracyjny.md`](../docs/panel-administracyjny.md).
