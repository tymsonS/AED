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

Zatrzymanie: `docker compose -f docker-compose.local.yml stop`. Dane zostają w wolumenach dockera.

## Co poprawiliśmy w kodzie z #57

Kod portalu w repo różnił się od oryginalnego archiwum w trzech miejscach, przez co docker się nie budował (poprawione na gałęzi `tymek/portal-docker-lokalnie`):
- 11 plików bez prawa wykonywania (m.in. skrypty startowe w `docker/`) – przywrócone jak w archiwum;
- brak pustych katalogów `logs/` i `media/` – przywrócone pliki-zaślepki z archiwum;
- `statics/` i paczka Fuseki – skrypt `aed_fetch_artifacts.sh`.

Do poprawy osobno (nie blokuje dockera): 16 plików ma zmienione końce linii (CRLF → LF) względem archiwum.
