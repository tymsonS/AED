# Portal lokalnie w dockerze – krok po kroku (AEDane)

Sprawdzone na Ubuntu 24.04 (Docker 29.1, Compose 2.40, 8 GB RAM). Oryginalna instrukcja portalu jest w `README.md` – ten plik dopisuje to, czego tam brakuje albo co nie działa od razu.

Komendy z kroków 1–6 uruchamiaj w katalogu `portal/`. Skrypty `aed_*.sh` działają z dowolnego katalogu.

## Czego potrzebujesz

- Docker i docker compose (`sudo apt-get install docker.io docker-compose-v2`, potem `sudo usermod -aG docker $USER` i ponowne zalogowanie).
- Ok. **20 GB wolnego dysku** (same obrazy to ok. 10 GB).
- Co najmniej **8 GB RAM**. Przy 8 GB uruchamiaj tylko potrzebne usługi (niżej).

## 1. Brakujące pliki

```bash
./aed_fetch_artifacts.sh                         # statics/ i paczka Fuseki z oryginalnego archiwum (sprawdza SHA-256)
cp mcod/settings/local.py.sample mcod/settings/local.py
```

W `mcod/settings/local.py` **usuń dwie linie `"timeout": 1,`** (w `ELASTICSEARCH_DSL_INDEX_SETTINGS` i `ELASTICSEARCH_HISTORIES_IDX_SETTINGS`). Elasticsearch 6.8 nie zna tej opcji i budowa indeksów kończy się błędem `unknown setting [index.timeout]`.

`local.py` i `.env` są w `.gitignore` – nie trafiają do repo.

## 2. Plik `.env`

```bash
cp env.sample .env
python3 -c "import secrets; print(secrets.token_hex(32))"   # wynik wpisz do FIELD_ENCRYPTION_KEYS
```

Zmień albo dopisz w `.env`:

```dotenv
DISCOURSE_FORUM_ENABLED=false                      # forum jest w prywatnym rejestrze dane.gov.pl
MAIN_DGA_DATASET_OWNER_ORGANIZATION_PK=2838        # instytucja z danych startowych
MAIN_AED_DATASET_OWNER_ORGANIZATION_PK=2838        # wykaz zbiorczy AED
MCOD_NGINX_WS=http://172.18.18.104:8001
MCOD_NGINX_PN_APPS=http://172.18.18.101:8001
MCOD_NGINX_API=http://172.18.18.102:8000
MCOD_NGINX_ADMIN=http://172.18.18.101:8001
MCOD_NGINX_CMS=http://172.18.18.103:8002
```

## 3. Nazwy w `/etc/hosts`

```bash
echo "172.18.18.100       mcod.local api.mcod.local admin.mcod.local cms.mcod.local forum.mcod.local mail.mcod.local" | sudo tee -a /etc/hosts
```

## 4. Budowa

```bash
COMPOSE_PARALLEL_LIMIT=1 docker compose -f docker-compose.local.yml build
```

`COMPOSE_PARALLEL_LIMIT=1` jest potrzebne: pięć usług zapisuje ten sam obraz `mcod-app:local` i przy budowie równoległej jedna kończy się błędem `image "mcod-app:local": already exists`. Pierwsza budowa trwa ok. 20–30 minut.

## 5. Baza, dane startowe, indeksy

```bash
docker compose -f docker-compose.local.yml up -d mcod-db mcod-redis mcod-rabbitmq mcod-elasticsearch mcod-rdfdb mcod-smtp
docker compose -f docker-compose.local.yml run --rm mcod-local-run python manage.py init_mcod_db      # migracje + dane startowe
docker compose -f docker-compose.local.yml run --rm mcod-local-run python manage.py search_index --rebuild -f
```

Pierwsze `run mcod-local-run` buduje jeszcze jeden obraz (kilkanaście minut). `README.md` portalu podaje przy indeksach samo `python manage.py` – właściwa komenda to `search_index --rebuild -f`.

## 6. Uruchomienie

```bash
docker compose -f docker-compose.local.yml up -d mcod-nginx mcod-local-admin mcod-local-api mcod-local-celery
```

- Panel: **https://admin.mcod.local** (przeglądarka ostrzeże o certyfikacie – to lokalny certyfikat z `docker/nginx/certs/`, można go zaakceptować).
- Konto: `admin@mcod.local`, hasło w `README.md` portalu, sekcja „Sprawdzenie statusu — Panel Administracyjny”.
- API: https://api.mcod.local/1.4/datasets

Bez forum (`mcod-discourse*`), Flower i kontenerów testowych całość zajmuje ok. 6 GB RAM.

**Strona publiczna `https://mcod.local` daje 502** – to normalne. Frontend portalu (Angular) jest osobnym projektem, nie ma go w `backend_latest.zip`; nginx szuka go pod `MCOD_NGINX_FRONTEND` (port 4200). Do pokazu wystarczą panel i API.

Zatrzymanie: `docker compose -f docker-compose.local.yml stop`. Dane zostają w wolumenach dockera.

## Komendy, które zapisują pliki – tylko przez `mcod-admin`

`mcod-local-run` **nie ma podpiętego katalogu `media/`**. Plik zapisany w nim (zasób dodany w `manage.py shell`, plik wykazu z `create_main_aed_resource_task`) znika razem z kontenerem, a celery zgłasza `FileNotFoundError`. Takie komendy uruchamiaj w działającym kontenerze panelu:

```bash
docker exec -i mcod-admin python manage.py shell -c "from mcod.resources.tasks.aed import create_main_aed_resource_task as t; t.apply()"
```

`mcod-local-run` zostaw do migracji, `init_mcod_db` i `search_index`.

## Demo: wykaz zbiorczy AED jedną komendą

Gdy portal działa (kroki 1–6):

```bash
./aed_demo.sh                  # pobiera świeże dane; bez sieci użyje danych pobranych wcześniej
```

**Bez internetu albo przy słabym łączu** (np. na pokazie):

```bash
./aed_demo.sh --pobierz        # raz, przy dobrym łączu: tylko dane 3 gmin do ingest/data/raw/ (portal niepotrzebny)
./aed_demo.sh --offline        # potem, bez sieci: demo z danych pobranych wcześniej
```

Sam portal działa lokalnie, więc demo z `--offline` nie potrzebuje internetu. Gdy zwykłe uruchomienie nie może pobrać danych, przechodzi na dane pobrane wcześniej i pisze o tym `UWAGA`. `--pobierz` bez internetu kończy się błędem, żeby nie było wątpliwości, czy dane są świeże.

Skrypt buduje pakiety dostawcy z `ingest/` dla 3 gmin, które publikują dane o AED na dane.gov.pl (Krosno, Przemyśl, Marki), kopiuje `aed.csv` do `portal/media/aed-demo/` i w kontenerze panelu (`aed_demo_wykaz.py`):
1. dodaje kategorię `HEAL` i instytucje dysponentów;
2. tworzy zbiory i zasoby z flagą „Zawiera wykaz defibrylatorów AED”;
3. czeka na walidację portalu (plik, dane, link);
4. uruchamia zadanie wykazu zbiorczego i wypisuje wynik.

Można go powtarzać – poprzednie dane demo są usuwane (tylko zbiory instytucji demo i wykaz instytucji-właściciela z ustawień; zbiór o podobnym tytule dodany ręcznie zostaje). Trwa ok. 20 sekund. Przykładowy wynik (prawdziwe dane, bez ręcznych poprawek; numery zbiorów i zasobów będą inne):

```text
  zasób 40226: plik SUCCESS, dane SUCCESS, link SUCCESS
  zasób 40227: plik SUCCESS, dane SUCCESS, link SUCCESS
  zasób 40228: plik SUCCESS, dane SUCCESS, link SUCCESS
Zadanie wykazu: SUCCESS
Wykaz zbiorczy: zbiór 4232, zasób 40229 – 50 AED
  Urząd Miasta Krosna: 21
  Urząd Miasta Marki: 8
  Urząd Miejski w Przemyślu: 21
  możliwy duplikat: Urząd Miasta Krosna – Zespół Krytych Pływalni (Krosno)
  możliwy duplikat: Urząd Miasta Marki – Szkoła Podstawowa nr 5 (Marki)
```

Komunikat `UWAGA: brak granic gmin` przy budowie pakietów nie przeszkadza w demo; pełne dane z gminą i województwem daje jednorazowe `python -m ingest fetch-gminy`.

## Harwester XML (ścieżka B) lokalnie – kod TERYT

Demo `aed_demo.sh` wgrywa zasoby bez harwestera, więc działa bez internetu i bez dodatkowych usług. Przy publikacji przez **harwester XML** (`docs/panel-administracyjny.md`, ścieżka B) portal sprawdza kod gminy z pliku (`<regions><terytIdent>`) w usłudze geokodowania **Pelias** (`GEOCODER_URL`, domyślnie `http://geocoder.mcod.local`). Tej usługi nie ma w kodzie portalu ani w docker compose. Lokalnie import kończy się wtedy komunikatem „Nieoczekiwany błąd walidacji schematu podczas importu danych” (w logu celery `KeyError: 'features'`).

To ograniczenie środowiska lokalnego: według kodu na dane.gov.pl kod TERYT sprawdza produkcyjny geokoder portalu (tego nie testowaliśmy). Do testu lokalnego wystarczy kopia `aed.xml` bez kodu TERYT – komendy w `docs/panel-administracyjny.md`, krok 2a. Tak sprawdzona ścieżka B: import bez błędów, zasób CSV z flagą wykazu AED ustawioną automatycznie, wykaz zbiorczy z 21 AED Krosna.

## Uwagi o danych dla portalu

- **Daty bez strefy czasowej.** Portal przyjmuje w danych tabelarycznych tylko daty bez strefy (`DATE_BASE_FORMATS` w `mcod/settings/base.py`, np. `yyyy-MM-dd'T'HH:mm:ss`). Data z `Z` albo `+00:00` daje przy walidacji danych `mapper_parsing_exception`. Dlatego `data_aktualizacji` we wzorcowym zakresie i w pakietach z `ingest/` to czas polski bez strefy, np. `2026-11-22T03:18:22`. Dotyczy to też prawdziwego dane.gov.pl.
- **Typy kolumn.** Portal sam zgaduje typy kolumn i kolumny tekstowe złożone z cyfr (`kod_teryt_gminy`, `numer_budynku`, `dysponent_regon`…) uznałby za liczby, a pusta komórka byłaby błędem. W zasobach z flagą AED i w samym wykazie nasza zmiana ustawia dla nich typ `string`. Na dane.gov.pl bez tej zmiany dostawca musiałby poprawić typy kolumn ręcznie w panelu.

## Różnice względem oryginalnego archiwum

Pliki oryginału w `portal/` są identyczne z `backend_latest.zip` (2.63.0), poza:
- `statics/` i paczką Fuseki – nie ma ich w repo ze względu na rozmiar, dogrywa je `aed_fetch_artifacts.sh`;
- naszymi zmianami: kod wykazu zbiorczego AED i flaga w harwesterze (opis w `README-AED.md`), dopiski w `.gitignore`, `portal/.gitattributes` z `* -text` (git nie zmienia końców linii, część plików ma CRLF, są też pliki binarne) oraz nasze pliki `aed_*`, `README-AED.md` i `README-DOCKER-AED.md`.
