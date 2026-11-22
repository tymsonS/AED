# Panel administracyjny portalu – instrukcja dla zespołu

> Na podstawie kodu backendu portalu (`backend_latest.zip`, projekt `mcod`) i jego `README.md`, 22.11.2026. Podział zadań (Tymek, #52): Tymek stawia docker compose, Krystian zajmuje się kodem portalu, Mikołaj panelem administracyjnym. **Instrukcja jest napisana z kodu i nie była jeszcze sprawdzona na działającym portalu.** Miejsca do sprawdzenia oznaczam „(sprawdzić)”.

Cel z podpowiedzi mentora: wiedzieć, **jak dodawać zasoby i automatyzować ich zasilanie**, a potem pokazać zbiorczą listę AED w portalu (wzór: Wykaz Główny DGA, `docs/analiza-wykazow-portalu.md`).

## 1. Wejście do panelu

- Adres: **https://admin.mcod.local** (usługa `mcod-local-admin`). Nazwy `mcod.local`, `api.mcod.local`, `admin.mcod.local`, `cms.mcod.local` trzeba skierować w pliku `hosts` na adres usługi `mcod-nginx` z `docker-compose.yml`. README portalu podaje `172.18.18.100`, a na macOS `127.0.0.1`. Na Windowsie wpis trafia do `C:\Windows\System32\drivers\etc\hosts` (sprawdzić adres przy Docker Desktop).
- Konta: dane startowe (`python manage.py init_mcod_db`, plik `mcod/core/fixtures/basic_data.json`) tworzą dwóch użytkowników. **Administrator** to `admin@mcod.local` (superuser), **pełnomocnik instytucji** to `pelnomocnik@mcod.local` (staff). Hasła są w `README.md` portalu, w sekcji „Sprawdzenie statusu – Panel Administracyjny”. Celowo ich tu nie przepisujemy.
- Dane startowe są minimalne: **1 instytucja** („Pierwsza instytucja”, pk 2838, typ `state`), **1 kategoria** (`AGRI`), 1 zbiór, 1 zasób i 1 źródło harwestera („Szczecin”, XML).

## 2. Przygotowanie słowników przed AED

| Co | Dlaczego | Gdzie w panelu |
|---|---|---|
| **Kategoria `HEAL` (Zdrowie)** | nasz pakiet dostawcy przypisuje zbiór do `HEAL`, a harwester szuka kategorii po kodzie (`Category.objects.filter(code__in=…)`, `mcod/harvester/models.py:536`). Bez niej zbiór AED nie dostanie kategorii | Kategorie → Dodaj (kod `HEAL`) (sprawdzić, czy dane startowe nie mają innej nazwy kodu) |
| **Instytucja dostawcy**, np. „Urząd Miasta Krosna”, typ samorządowy (`local`) | źródło harwestera i zbiór należą do instytucji; w wykazie DGA typ instytucji ma znaczenie (`ALLOWED_DGA_INSTITUTIONS`: `local`, `state`) | Instytucje → Dodaj; można też użyć „Pierwszej instytucji” |

## 3. Ścieżka A: zbiór i zasób dodane ręcznie

Dla jednorazowej publikacji, tak jak robi mała gmina:
1. **Zbiory danych → Dodaj:** tytuł „Lokalizacje defibrylatorów AED – Krosno”, instytucja, kategoria `HEAL`, licencja CC BY 4.0, częstotliwość aktualizacji.
2. **Zasoby → Dodaj** w tym zbiorze: plik `aed.csv` z pakietu (`ingest/data/pakiety/aed-1861011/`), format CSV. Portal sam uruchomi walidację pliku, danych i linku (`data_tasks`, `file_tasks`, `link_tasks`). Ich wynik „SUCCESS” jest warunkiem udziału zasobu w wykazie zbiorczym (`dga_utils.py:254`).
3. To samo dla `aed.geojson`. Przy CSV w opcjach mapy wskazujemy kolumny `dlugosc_geo` i `szerokosc_geo` (`CZYTAJ-MNIE.txt` pakietu).

## 4. Ścieżka B: harwester XML, czyli automatyczne zasilanie

To jest „automatyzacja zasilania”, o którą pytał mentor. Nasz pakiet dostawcy jest pod nią przygotowany: `aed.xml` w schemacie 1.13 i `aed.md5`.

**Co harwester sprawdza przy adresie XML** (`mcod/harvester/utils.py:227`, `validate_xml_url`):
- adres odpowiada na `HEAD`;
- nazwa kończy się na `.xml` i nie ma spacji;
- nagłówek `Content-Type` zawiera `text/xml` albo `application/xml`;
- obok leży **plik `.md5` o tej samej nazwie** (`aed.xml` → `aed.md5`), a jego suma zgadza się z pobranym XML;
- XML przechodzi walidację XSD (wersja wykrywana z przestrzeni nazw, u nas `1.13`).

**Adresy muszą być `https://`**, bo wymaga tego XSD (`xs:pattern value="https://.*"`). Lokalnie najprościej wystawić pakiet przez nginx portalu. Serwuje on katalog `media/` repozytorium portalu pod `https://mcod.local/media/` (`docker/nginx/config-templates/01-frontend.conf.template`, `location /media`), a kontener celery instaluje lokalne certyfikaty do połączeń HTTPS (README portalu: „połączenia między kontenerami”).

Kroki:
1. **Pakiet z właściwym adresem bazowym** (adres trafia do XML, więc musi wskazywać miejsce, z którego portal pobierze pliki):
   ```bash
   python -m ingest package danegovpl-krosno --teryt 1861011 --gmina "Krosno" \
       --dostawca "Urząd Miasta Krosna" --base-url https://mcod.local/media/aed-krosno/
   ```
   Sprawdzone 22.11: pakiet z tym adresem przechodzi naszą walidację (0 błędów) i XSD portalu 1.13, a w `aed.xml` są adresy `https://mcod.local/media/aed-krosno/aed.csv` i `…/aed.geojson`.
2. **Skopiować pliki pakietu** (`aed.xml`, `aed.md5`, `aed.csv`, `aed.geojson`) do `media/aed-krosno/` w katalogu portalu. Sprawdzić w przeglądarce, że `https://mcod.local/media/aed-krosno/aed.xml` się otwiera.
3. **Panel → Źródła danych (harwester) → „Walidacja XML”** (`/validate_xml/`, `ValidateXMLDataSourceView`): podać adres `aed.xml`. Portal sprawdzi to samo co przy imporcie i pokaże błędy, zanim cokolwiek zapisze.
4. **Źródła danych → Dodaj:**
   - nazwa, np. „Krosno – AED”;
   - typ **XML**;
   - adres XML;
   - instytucja;
   - **częstotliwość** (co 1, 7, 30 albo 90 dni);
   - adresy e-mail do raportów.

   Pola formularza: `mcod/harvester/admin.py:238`.
5. **Status „aktywne” i zapis.** Zmiana statusu na aktywny od razu uruchamia import (`import_data_task`, komunikat „Import data task was launched!”, `admin.py:232`). Wynik jest w zakładce **Importy**, a utworzone zbiory w zakładce **Zbiory danych** źródła.
6. Po zmianie danych wystarczy zbudować pakiet od nowa (zmieni się `aed.md5`) i podmienić pliki. Portal pobierze je przy kolejnym przebiegu albo po ponownej aktywacji.

Uwaga: po utworzeniu źródła **adres XML i typ są w formularzu zablokowane** (`forms.py:63`). Zmiana adresu oznacza nowe źródło.

## 5. Wykaz zbiorczy – próba na istniejącym wzorze DGA

Zanim dopiszemy flagę AED, warto zobaczyć cały mechanizm w działaniu na DGA:
1. W zasobie zaznaczyć **„Zawiera wykaz chronionych danych”** (`contains_protected_data`, zakładka zasobu w `mcod/resources/admin.py:532`). Plik musi mieć kolumny `Lp.`, `Zasób chronionych danych`, `Format danych`, `Rozmiar danych`, `Warunki ponownego wykorzystywania`, a instytucja musi być typu `local` albo `state`.
2. Ustawić zmienną środowiskową **`MAIN_DGA_DATASET_OWNER_ORGANIZATION_PK`** na pk istniejącej instytucji, np. `2838`. Domyślne `333` lokalnie nie istnieje (`settings/base.py:1714`, README portalu).
3. Uruchomić zadanie bez czekania na 3:30 (sprawdzić):
   ```bash
   docker compose -f docker-compose.local.yml run mcod-local-run python manage.py shell -c \
     "from mcod.resources.tasks.dga import create_main_dga_resource_task as t; t.apply()"
   ```
4. W panelu powinien pojawić się zbiór „Wykaz zasobów chronionych danych DGA – raport zbiorczy” z zasobem XLSX. Ten sam przebieg będzie miał później wykaz AED.

## 6. Do demo „do odczytu”

Mentor: jury może nie mieć dostępu do wszystkich domen. Z lokalnego portalu robimy zrzuty ekranu albo krótkie nagranie:
1. walidacja XML pakietu Krosna w panelu, bez błędów;
2. źródło harwestera „Krosno – AED” aktywne, import zakończony;
3. zbiór i zasoby AED na stronie `https://mcod.local`, z mapą z CSV;
4. później: wykaz zbiorczy AED jako zasób portalu.

## Do sprawdzenia po postawieniu portalu

- Czy kontener celery rozwiązuje `mcod.local` i ufa lokalnemu certyfikatowi przy pobieraniu z `media/`?
- Czy nginx podaje `aed.xml` z `Content-Type: text/xml`?
- Jak nazywa się kategoria „Zdrowie” i czy kod `HEAL` jest wymagany w tej postaci?
- Czy `t.apply()` w punkcie 5 działa bez działającego workera celery, czy trzeba użyć `t.delay()` przy działającym `mcod-local-celery`?
