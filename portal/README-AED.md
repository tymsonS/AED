# portal/ – kod źródłowy portalu dane.gov.pl w projekcie AEDane

Oryginalny `README.md` w tym katalogu to dokumentacja portalu (konfiguracja środowiska, docker compose). Ten plik opisuje, skąd jest kod i co w nim zmieniamy.

## Skąd jest kod

- **Źródło:** https://dane.gov.pl/source-code/backend_latest.zip, czyli backend portalu (projekt `mcod`, Django).
- **Wersja:** 2.63.0 z 28.10.2026 (`CHANGELOG.md`), archiwum z 09.11.2026, SHA-256 `85949002eaa9f96c4dc2207c9a62caa29e5eae55d5ea5e9bd78a179ce0c3f47a`.
- **Licencja:** GPL v3. Nasze zmiany w tym katalogu też są na GPL v3.
- **Pierwszy commit `portal/` to oryginał bez zmian.** Tak radził mentor („rozpakowany kod źródłowy jako pierwszy commit, a następnie własny przyrost w kolejnych commitach”), więc nasze zmiany widać w historii gita jako różnicę względem oryginału.
- **Pominięte** tylko duże artefakty binarne, które są w oryginalnym archiwum:
  - `statics/` – zbudowany frontend, 78 MB;
  - `docker/rdfdb/fuseki/dist/` – paczka Apache Jena Fuseki, 51 MB.

  Do środowiska dockera dogrywa je `portal/aed_fetch_artifacts.sh` (z oryginalnego archiwum, z kontrolą SHA-256).

## Po co

Podpowiedź mentorów hackathonu: najważniejsze jest **dostosowanie i przebudowanie logiki i metod w portalu**, żeby „wykazy” zasobów wielu dostawców dało się pobierać i scalać w jedną standardową listę. Wzorem jest **Wykaz Główny DGA**: instytucje publikują zasoby z flagą, a portal codziennie skleja je w jeden zasób zbiorczy. Analiza z odwołaniami do kodu: [`docs/analiza-wykazow-portalu.md`](../docs/analiza-wykazow-portalu.md).

## Nasze zmiany

### Wykaz zbiorczy AED

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
| `mcod/resources/tasks/process_resource_file_data.py` | przy zasobie z flagą AED i przy samym wykazie kolumny tekstowe wzorcowego zakresu (`kod_teryt_gminy`, `numer_budynku`, `dysponent_regon`…) mają typ `string` zamiast zgadywanego typu liczbowego; inaczej pusta komórka jest błędem walidacji | – |
| `mcod/resources/tests/test_aed_merge.py` | 14 testów scalania i typów kolumn (bez bazy danych) | – |

Wynik: kolumny wzorcowego zakresu AED i do tego `instytucja_publikujaca`, `id_zasobu_zrodlowego`, `mozliwy_duplikat` (odpowiednik „Nazwa dysponenta zasobu” w DGA).

**Weryfikacja na portalu uruchomionym lokalnie** ([`README-DOCKER-AED.md`](README-DOCKER-AED.md)): prawdziwe pakiety dostawcy z `ingest/` dla Krosna, Przemyśla i Marek przechodzą walidację portalu (plik, dane, link) bez ręcznych poprawek; wykaz ma **50 AED** (21 + 21 + 8), a AED z Marek ze współrzędnymi pływalni w Krośnie (błąd w danych źródłowych) jest oznaczony jako możliwy duplikat. Testy scalania (`test_aed_merge.py`) działają bez bazy danych.

### Demo jedną komendą

Na postawionym portalu cały przebieg (3 gminy, zasoby z flagą, walidacja, wykaz zbiorczy) uruchamia `portal/aed_demo.sh`. Bez internetu, np. na pokazie: najpierw raz `portal/aed_demo.sh --pobierz`, potem `portal/aed_demo.sh --offline`. Szczegóły i wynik: [„Demo” w `README-DOCKER-AED.md`](README-DOCKER-AED.md#demo-wykaz-zbiorczy-aed-jedną-komendą).

### Jak uruchomić ręcznie (na postawionym portalu)

1. `python manage.py migrate resources` (migracja `0076_aedane_wykaz_aed`).
2. Zmienna środowiskowa **`MAIN_AED_DATASET_OWNER_ORGANIZATION_PK`**: pk instytucji-właściciela wykazu. Lokalnie np. `2838` („Pierwsza instytucja” z danych startowych), bo domyślne `333` lokalnie nie istnieje. Kategoria o kodzie `HEAL` musi istnieć (dane startowe mają tylko `AGRI`).
3. W panelu zasoby AED gmin, np. `aed.csv` z pakietu dostawcy z `ingest/`, oznaczyć **„Zawiera wykaz defibrylatorów AED”** i poczekać na udaną walidację zasobu.
4. Uruchomić zadanie bez czekania na 4:00:
   ```bash
   docker exec -i mcod-admin python manage.py shell -c "from mcod.resources.tasks.aed import create_main_aed_resource_task as t; t.apply()"
   ```
   W działającym kontenerze panelu, nie w `mcod-local-run`: ten nie ma podpiętego `media/`, więc plik wykazu zniknąłby razem z kontenerem.
5. Wynik: zbiór **„Wykaz zbiorczy defibrylatorów AED”** z zasobem CSV.

### Flaga AED w harwesterze XML (schemat 1.14)

Flaga „Zawiera wykaz defibrylatorów AED” może przyjść w pliku harwestera, więc nie trzeba jej zaznaczać ręcznie w panelu przy każdym zasobie. Wysyła ją pakiet dostawcy (`python -m ingest package … --wykaz-aed`, opis w `ingest/README.md`), a harwester sam włącza zasób do wykazu zbiorczego.

| Plik | Co robi |
|---|---|
| `data/harvester/xml_import_otwarte_dane_1_14.xsd` | kopia 1.13 z przestrzenią nazw `urn:otwarte-dane:harvester:1.14` i jednym nowym, opcjonalnym elementem zasobu **`containsAedData`** (`xs:boolean`, domyślnie `false`) zaraz po `containsProtectedData` |
| `mcod/settings/base.py` | wersja `1.14` w `HARVESTER_XML_VERSION_TO_SCHEMA_PATH` |
| `mcod/harvester/serializers.py` | pole `contains_aed_data` (`containsAedData`) w `XMLResourceSchema`; harwester przepisuje je do zasobu tak jak `containsProtectedData` (`_create_or_update_if_changed_resource`) |
| `data/test_samples/harvester/import_example1.14.xml`, `mcod/harvester/tests/test_serializers.py`, `test_schemas.py` | próbka 1.14 (drugi zasób z flagą) i testy: 1.14 czyta flagę, 1.13 jej nie przyjmuje, mapowanie pola, `updateFrequency` w 1.14 |

Pliki w wersji 1.13 i starszych działają bez zmian. Flaga ma w nich wartość `false`, tak jak brak `containsProtectedData`.

**Weryfikacja:**
- testy harwestera (`mcod/harvester/tests`, w kontenerze `mcod-local-tests`): **200 passed, 2 xfailed**, w tym testy wersji 1.14: plik 1.14 z flagą przechodzi XSD, ta sama treść w 1.13 jest odrzucana, stare pliki 1.13 działają;
- testy scalania wykazu (`mcod/resources/tests/test_aed_merge.py`): **14 passed**;
- na portalu lokalnym import z harwestera pakietu Krosna z `--wykaz-aed` ustawia flagę przy zasobie CSV automatycznie (GeoJSON bez flagi), a wykaz zbiorczy ma **21 AED Krosna** z `id_zasobu_zrodlowego` = zasób z harwestera.

**Uwaga – kod TERYT na portalu lokalnym:** przy `<regions><terytIdent>` portal sprawdza kod w usłudze geokodowania Pelias, której nie ma w docker compose. Lokalnie import z kodem TERYT się nie uda – obejście w [`docs/panel-administracyjny.md`](../docs/panel-administracyjny.md), krok 2a. Na dane.gov.pl kod sprawdza – według kodu – produkcyjny geokoder portalu (tego nie testowaliśmy).

### Możliwe dalsze kroki
- walidacja pliku przy zaznaczeniu flagi w formularzu (wymagane kolumny), jak `_validate_dga_file`;
- flaga w API i serializerach zasobu.

Panel administracyjny i harwester (dodawanie zasobów, automatyczne zasilanie pakietem dostawcy z `ingest/`): [`docs/panel-administracyjny.md`](../docs/panel-administracyjny.md).
