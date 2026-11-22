# „Wykazy” w portalu dane.gov.pl – wzór dla zbiorczej listy AED

> Rozpoznanie 22.11.2026 na podstawie kodu backendu portalu (`https://dane.gov.pl/source-code/backend_latest.zip`, projekt `mcod`, licencja GPL v3). Ścieżki i numery linii odnoszą się do tego archiwum, nie do naszego repo.

**Podpowiedź mentora** (Discord, 21.11, ok. 23:30): dane mają być zasobami na dane.gov.pl, rozproszonymi po wielu dostawcach, więc „musi powstać zbiorcza tabela”. Wprost: „są pewne **wykazy** w portalu, których rozwiązanie jest podobne – zobaczcie je i spróbujcie odtworzyć ich logikę na podstawie kodu”. Najważniejsze jest **przebudowanie logiki portalu**, a nie sama aplikacja zbierająca dane.

## Wniosek

W portalu działa dokładnie taki mechanizm: **Wykaz Główny DGA**, czyli zbiorczy wykaz zasobów chronionych danych (Data Governance Act).
- Każda instytucja publikuje **jeden zasób w ustalonym układzie kolumn** i oznacza go flagą „zawiera wykaz chronionych danych”.
- **Codziennie o 3:30 zadanie Celery** zbiera wszystkie takie zasoby, sprawdza je, skleja w jedną tabelę z kolumną „Nazwa dysponenta zasobu” i **publikuje wynik jako zasób portalu** w zbiorze „Wykaz zasobów chronionych danych DGA – raport zbiorczy”.

Dla AED da się to odtworzyć prawie jeden do jednego, a nasze dotychczasowe elementy (schemat, walidator, pakiet dostawcy, reguły scalania z `ingest/`) dokładnie pasują do tego wzoru.

## Jak działa Wykaz Główny DGA

| Krok | Gdzie w kodzie | Co robi |
|---|---|---|
| 1. Flaga zasobu | `mcod/resources/models.py:579` – `contains_protected_data = BooleanField(...)` | zasób oznaczony jako „wykaz chronionych danych” instytucji |
| 2. Wzorcowy układ kolumn | `mcod/resources/dga_constants.py` – `DGA_COLUMNS` | `Lp.`, `Zasób chronionych danych`, `Format danych`, `Rozmiar danych`, `Warunki ponownego wykorzystywania`; pliki `xlsx`, `xls`, `csv` |
| 3. Walidacja przy dodaniu zasobu | `mcod/resources/forms.py:286` (`clean`), `:402` (`_validate_dga_file`), `:387` (typ instytucji), `:454` | sprawdza nazwy i kolejność kolumn (`dga_utils.validate_dga_df_columns`), dopuszcza tylko instytucje samorządowe i państwowe (`ALLOWED_DGA_INSTITUTIONS`) i **jeden** taki zasób na instytucję (flaga zdejmowana z poprzedniego) |
| 4. Zasilanie automatyczne | harwester XML: element `containsProtectedData` w XSD 1.12 i 1.13 (`data/harvester/xml_import_otwarte_dane_1_13.xsd:666`), `dga_utils.py:893`; harwester CKAN: `mcod/harvester/ckan_utils.py:118` | flaga przychodzi razem z zasobem od dostawcy, bez ręcznej pracy w panelu |
| 5. Wybór źródeł | `dga_utils.py:234` – `get_all_dga_resources_sorted_by_organizations` | opublikowane zasoby z flagą i z udaną walidacją danych, pliku i linku (`*_tasks_last_status == "SUCCESS"`), bez samego wykazu głównego |
| 6. Odczyt i kontrola | `dga_utils.py:371` (`get_main_dga_source_df`), `:316`, `:328`, `:360` | wymagane kolumny (`MAIN_DGA_REQUIRED_SOURCE_COLUMNS`), przycięcie tekstu, brak pustych wartości wymaganych; zasób z błędem jest **pomijany z logiem**, nie przerywa całości |
| 7. Scalenie | `dga_utils.py:401` – `create_main_dga_df` | `pd.concat`, kolumna „Nazwa dysponenta zasobu” = instytucja zasobu, numeracja `Lp.` |
| 8. Plik wynikowy | `dga_utils.py:514` – `create_main_dga_file` | XLSX z nazwą z datą (`settings.MAIN_DGA_XLSX_FILE_NAME_PREFIX`), stylizacja |
| 9. Publikacja jako zasób | `mcod/resources/tasks/dga.py:32` – `create_main_dga_resource_task`; `dga_utils.py:705`, `:786` | tworzy zasób (i w razie potrzeby zbiór) instytucji-właściciela (`MAIN_DGA_DATASET_OWNER_ORGANIZATION_PK`), czeka na walidację portalu, podmienia stary zasób; przy błędzie sprząta |
| 10. Jeden wpis „gdzie jest wykaz” | `mcod/resources/models.py:1628` – `AggregatedDGAInfo` (singleton) | wskazuje aktualny zasób wykazu głównego |
| 11. Harmonogram | `mcod/celeryapp.py:88` – `dga_main_resource_creation`, `crontab(minute=30, hour=3)` | codziennie |
| 12. Strona w portalu | `mcod/cms/models/dga.py:103` – `DGAProtectedDataList` | podstrona CMS „Wykaz danych chronionych” |
| 13. API i metadane | `mcod/resources/serializers.py:152`, `:537`, `:628` | flaga widoczna w API i w metadanych zasobu |

Drugi „wykaz” w kodzie, czyli dane wysokiej wartości z wykazu KE (`has_high_value_data_from_ec_list`), to tylko flaga przy zasobie i zbiorze, bez agregacji. Wzorem jest więc DGA.

## Wykaz zbiorczy AED – jak odtworzyliśmy ten wzór

Zrobione w `portal/` (#58, opis plików w [`portal/README-AED.md`](../portal/README-AED.md)), sprawdzone na portalu uruchomionym lokalnie (#61, #67).

| Element DGA | Odpowiednik dla AED | Stan |
|---|---|---|
| `contains_protected_data` | flaga zasobu `contains_aed_data` („Zawiera wykaz defibrylatorów AED”) w modelu i formularzu panelu, z migracją | ✅ |
| `DGA_COLUMNS` | kolumny wzorcowego zakresu danych AED (`schema/aed.schema.json`, 41 pól) | ✅ `mcod/resources/aed_merge.py` |
| walidacja kolumn w formularzu | wymagane kolumny sprawdzane przy sklejaniu; zasób bez nich jest pomijany z logiem | ✅ przy sklejaniu, ❌ w formularzu |
| typ instytucji (`local`, `state`) | dysponenci AED to też szkoły, szpitale i firmy, więc wykaz AED nie ogranicza typu instytucji | ✅ |
| harwester: `containsProtectedData` | nowy element `containsAedData` w XSD | ✅ schemat 1.14 w `portal/` (#76) i `python -m ingest package … --wykaz-aed`; dzisiejszy dane.gov.pl zna tylko 1.13, więc tam flagę zaznacza się w panelu |
| wybór źródeł i odczyt z pomijaniem błędnych | opublikowane zasoby z flagą i udaną walidacją portalu; pojedyncze błędne wiersze pomijane z powodem | ✅ |
| scalenie `pd.concat` + dysponent | scalenie po `id_aed`, kolumny `instytucja_publikujaca`, `id_zasobu_zrodlowego`, a AED różnych instytucji bliżej niż 50 m oznaczane w `mozliwy_duplikat` | ✅ |
| XLSX wykazu głównego | jeden zasób CSV | ✅ |
| zbiór „raport zbiorczy” instytucji-właściciela | zbiór „Wykaz zbiorczy defibrylatorów AED” instytucji z `MAIN_AED_DATASET_OWNER_ORGANIZATION_PK`, kategoria `HEAL` | ✅ (właściciel na produkcji – pytanie do mentorów) |
| `AggregatedDGAInfo` + zadanie Celery 3:30 | `AggregatedAEDInfo` + `create_main_aed_resource_task` codziennie o 4:00; pusty wynik nie zastępuje poprzedniego wykazu | ✅ |
| typy kolumn przy walidacji danych | kolumny tekstowe AED (TERYT, REGON, numer budynku…) mają typ `string` zamiast zgadywanego | ✅ (`process_resource_file_data.py`) |
| API i serializery | flaga widoczna w API zasobu | ❌ |
| strona CMS | podstrona z mapą zbiorczą, czyli moduł „Znajdź AED” (`app/`) | prototyp poza portalem |

**Czego wzór DGA nie ma, a AED potrzebuje – i mamy:**
- **Duplikaty:** DGA tylko skleja wiersze, a ten sam AED może być w zasobie gminy i w zasobie szpitala. Wykaz AED scala rekordy o tym samym `id_aed`, a bliskie AED różnych instytucji oznacza zamiast usuwać – rozstrzyga dysponent.
- **Status weryfikacji:** wykaz zachowuje kolumny `lokalizacje_potwierdzil` i `metoda_weryfikacji` ze schematu v0.2.

## Wynik

- Prawdziwe pakiety dostawcy z `ingest/` dla Krosna, Przemyśla i Marek przechodzą walidację portalu bez ręcznych poprawek; wykaz ma **50 AED**, a AED z Marek leżący w Krośnie jest oznaczony jako możliwy duplikat.
- Cały przebieg uruchamia `portal/aed_demo.sh` (także bez internetu: `--pobierz`, potem `--offline`).
- Na dane.gov.pl zmianę musiałoby wdrożyć Ministerstwo Cyfryzacji.

## Pytania do mentorów

- Kto powinien być właścicielem zbioru zbiorczego (odpowiednik `MAIN_DGA_DATASET_OWNER_ORGANIZATION_PK`)?
