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

## Nasze zmiany (plan)

**Wykaz zbiorczy AED** na wzorze DGA (`mcod/resources/dga_*.py`, `mcod/resources/tasks/dga.py`):
1. flaga zasobu „zawiera wykaz AED” w modelu, formularzu, API i harwesterze XML;
2. kolumny i walidacja według wzorcowego zakresu danych AED (`schema/aed.schema.json`, reguły z `ingest/validate.py`);
3. codzienne zadanie Celery, które skleja zasoby z flagą w jeden zasób „Wykaz zbiorczy defibrylatorów AED”, z usuwaniem duplikatów i poziomami zaufania z `ingest/`.

Panel administracyjny i harwester (dodawanie zasobów, automatyczne zasilanie pakietem dostawcy z `ingest/`): [`docs/panel-administracyjny.md`](../docs/panel-administracyjny.md).
