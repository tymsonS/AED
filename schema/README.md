# schema/ – wzorcowy zakres danych o AED (v0.1)

Kontrakt danych między `ingest/` a `app/` (patrz `AGENTS.md`). Zmiana nazwy lub typu pola wymaga zgody właścicieli obu obszarów.

| Plik | Co to jest |
|---|---|
| `aed.schema.json` | **Źródło prawdy.** Frictionless Table Schema: 39 pól, typy, ograniczenia, poziomy (`x-poziom`), grupy (`x-grupa`). |
| `wzorcowy-zakres-danych-aed.xlsx` | Plik do oddania (wymóg formalny zadania). Generowany – nie edytuj ręcznie. |
| `przyklad-aed.csv` | 3 poprawne, **fikcyjne** rekordy (nazwy, telefony, REGON/NIP są zmyślone; REGON/NIP mają poprawne sumy kontrolne). |
| `build_xlsx.py` | Generuje XLSX ze schematu i przykładu. |
| `tests/test_schema.py` | Testy spójności schematu i przykładu (bez sieci). |
| `tests/test_frictionless.py` | Pełna walidacja biblioteką `frictionless`: schemat, CSV, XLSX, plik dysponenta. |

## Jak używać

```bash
python schema/build_xlsx.py        # po każdej zmianie aed.schema.json lub przykladu
python -m pytest schema/tests      # wymaga: frictionless, openpyxl, pytest
```

**Pełna walidacja biblioteką `frictionless`** (`tests/test_frictionless.py`) – biblioteka jest wymagana; bez niej testy kończą się błędem (nie są pomijane). Wszystkie testy muszą przechodzić (0 `skipped`, 0 `failed`):

```bash
pip install "frictionless>=5,<6" openpyxl pytest
python -m pytest schema/tests -v -rs
```

XLSX ma trzy arkusze: **Dane** (pusty szablon dla dysponenta z listami rozwijanymi; kolor nagłówka = poziom pola, opis w komentarzu komórki; kolumna `id_aed` oznaczona „nadaje system” i zablokowana przed wpisywaniem), **Słownik** (opis każdego pola), **Przykład** (3 rekordy w postaci zbioru wynikowego, więc z `id_aed`).

## Poziomy pól

- **wymagane** – bez nich rekord jest odrzucany,
- **zalecane** – brak lub błąd daje ostrzeżenie,
- **opcjonalne** – można pominąć.

## Plik od dysponenta a zbiór wynikowy (`id_aed`)

`aed.schema.json` opisuje **zbiór wynikowy** publikowany na dane.gov.pl. Pole z `"x-nadaje-system": true` (obecnie tylko `id_aed`) nadaje `ingest/` przy scalaniu, zgodnie z planem technicznym (decyzja Krystiana z 21.11.2026: wariant z planu):

- **plik od dysponenta** (arkusz „Dane”, upload w walidatorze) – pole zostaje puste; dysponenta i urządzenie identyfikuje para `zrodlo` + `id_zrodlowe`;
- **zbiór wynikowy** – pole wymagane i unikalne (klucz główny), stałe między odświeżeniami (mapa `id_zrodlowe → id_aed` w `ingest/`).

Walidator `ingest/` sprawdza plik od dysponenta schematem pochodnym: ten sam `aed.schema.json`, ale bez `primaryKey` i bez `required` w polach z `x-nadaje-system`. Wpisana wartość w takim polu to błąd (dysponent nie nadaje identyfikatorów). Testy w `tests/test_frictionless.py` pokazują to na przykładzie.

## Reguły biznesowe (do zaimplementowania w walidatorze `ingest/`)

Table Schema nie wyraża tych reguł, więc opisujemy je tutaj. Testy w `tests/` sprawdzają część z nich na przykładzie.

| Reguła | Skutek |
|---|---|
| `godziny_dostepnosci` w składni `opening_hours` (OSM) albo dokładnie `nieznane` | błąd |
| `dostepny_24h`: `tak` ⇔ godziny `24/7`; `nieznane` ⇔ godziny `nieznane`; w pozostałych przypadkach `nie` | błąd |
| `data_przegladu` starsza niż 12 miesięcy od daty walidacji | ostrzeżenie |
| `data_waznosci_elektrod` lub `data_waznosci_baterii` w przeszłości | ostrzeżenie |
| Podany co najmniej jeden z: `dysponent_regon`, `dysponent_nip` | ostrzeżenie |
| Poprawna suma kontrolna REGON (9 lub 14 cyfr) i NIP | błąd |
| Współrzędne wewnątrz granic Polski i w gminie z `kod_teryt_gminy` | błąd / ostrzeżenie |
| Unikalne `id_zrodlowe` w obrębie jednego źródła | błąd |
| Pole z `x-nadaje-system` (`id_aed`) wypełnione w pliku od dysponenta | błąd |
| `zrodlo` – identyfikatory istniejące w `ingest/sources.yaml` | błąd |
| `telefon_kontaktowy` – tylko numer instytucji, nigdy osoby prywatnej (RODO) | weryfikacja przy imporcie |
| Kod do szafki nigdy nie trafia do danych – tylko `kod_do_szafki_u_dyspozytora` = tak/nie | – |

## Zmiany względem tabeli w `docs/plan-techniczny.md`

Decyzje Krystiana z 21.11.2026:
1. `godziny_dostepnosci` zostaje wymagane, ale przyjmuje wartość `nieznane` – rekordy bez godzin nie są odrzucane. W konsekwencji `dostepny_24h` ma wartości `tak` / `nie` / `nieznane` (zamiast tak/nie).
2. Reguła dat: ostrzeżenie, gdy przegląd jest starszy niż 12 miesięcy oraz gdy elektrody lub bateria straciły ważność (zamiast „data przeglądu nie w przeszłości”).
3. `id_aed`: przyjęta propozycja z planu – puste w pliku od dysponenta, wymagane w zbiorze wynikowym (sekcja wyżej).

Doprecyzowania techniczne: `dysponent_regon` i `dysponent_nip` to dwie osobne kolumny; rekord scalony z kilku źródeł ma w `zrodlo` identyfikatory rozdzielone `;`; `licencja` to identyfikator SPDX (np. `CC-BY-4.0`).
