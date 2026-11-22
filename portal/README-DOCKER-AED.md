# Portal lokalnie w dockerze – krok po kroku (AEDane)

Sprawdzone 22.11.2026 na Ubuntu 24.04 (Docker 29.1, Compose 2.40, 8 GB RAM). Oryginalna instrukcja portalu jest w `README.md` – ten plik dopisuje to, czego tam brakuje albo co nie działa od razu.

Wszystkie komendy uruchamiaj w katalogu `portal/`.

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
MAIN_AED_DATASET_OWNER_ORGANIZATION_PK=2838        # wykaz zbiorczy AED (#58)
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

## Komendy, które zapisują pliki – tylko przez `mcod-admin`

`mcod-local-run` **nie ma podpiętego katalogu `media/`**. Plik zapisany w nim (zasób dodany w `manage.py shell`, plik wykazu z `create_main_aed_resource_task`) znika razem z kontenerem, a celery zgłasza `FileNotFoundError`. Takie komendy uruchamiaj w działającym kontenerze panelu:

```bash
docker exec -i mcod-admin python manage.py shell -c "from mcod.resources.tasks.aed import create_main_aed_resource_task as t; t.apply()"
```

`mcod-local-run` zostaw do migracji, `init_mcod_db` i `search_index`.

## Test wykazu zbiorczego AED (#58) – wynik 22.11.2026

Kategoria `HEAL`, dwie instytucje (Krosno, Marki), zasoby `aed.csv` z pakietów `ingest/` z flagą „Zawiera wykaz defibrylatorów AED”, potem zadanie wykazu:
- migracja `0076_aedane_wykaz_aed` – OK;
- zbiór „Wykaz zbiorczy defibrylatorów AED” (kategoria Zdrowie) z zasobem CSV: **29 AED** (21 Krosno + 8 Marki), 44 kolumny;
- AED z Marek ze współrzędnymi pływalni w Krośnie i AED pływalni oznaczone wzajemnie w `mozliwy_duplikat`.

Dwie rzeczy, przez które pliki z `ingest/` **nie przechodziły walidacji danych portalu** (dotyczy też prawdziwego dane.gov.pl):
1. **Data ze strefą czasową – nadal otwarte.** Portal przyjmuje w danych tabelarycznych tylko daty bez strefy (`DATE_BASE_FORMATS` w `mcod/settings/base.py`: m.in. `yyyy-MM-dd'T'HH:mm:ss`, bez `Z` i `+00:00`). `data_aktualizacji` z pakietu (`2026-11-22T00:30:37+00:00`) daje `mapper_parsing_exception`. W teście użyto kopii plików z datą bez strefy. Propozycja Mikołaja (czas polski bez strefy w schemacie i w `ingest/`) czeka na decyzję właściciela `schema/` – komentarz w #61.
2. **Zgadywanie typów kolumn – rozwiązane w #58 (`ede3507`).** Portal sam zgaduje typy; kolumny tekstowe z samymi cyframi i pustymi komórkami (`numer_budynku`, `kod_teryt_gminy`, `dysponent_regon` …) uznawał za liczby, a pusta komórka była wtedy błędem. Teraz zasoby z flagą AED i sam wykaz dostają typ `string` dla kolumn tekstowych wzorcowego zakresu. **Sprawdzone ponownie na portalu (22.11):** zasoby Krosna i Marek oraz wykaz (29 AED) przechodzą walidację danych bez ręcznych poprawek.

Zatrzymanie: `docker compose -f docker-compose.local.yml stop`. Dane zostają w wolumenach dockera.

## Co poprawiliśmy w kodzie z #57

Kod portalu w repo różnił się od oryginalnego archiwum w trzech miejscach, przez co docker się nie budował (poprawione na gałęzi `tymek/portal-docker-lokalnie`):
- 10 plików bez prawa wykonywania (m.in. skrypty startowe w `docker/`, `manage.py`) – przywrócone jak w archiwum (`sample.bat` jest w archiwum zapisany bez uniksowych praw, więc zostaje bez `+x`);
- brak pustych katalogów `logs/` i `media/` – przywrócone pliki-zaślepki z archiwum;
- `statics/` i paczka Fuseki – skrypt `aed_fetch_artifacts.sh`.

Do poprawy osobno (nie blokuje dockera): 16 plików ma zmienione końce linii (CRLF → LF) względem archiwum, w tym uszkodzony przez to `data/test_samples/example.pdf`. Poprawi to Mikołaj osobnym PR (`.gitattributes` z `-text`).
