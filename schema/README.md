# schema/ – wzorcowy zakres danych o AED (v0.2)

Kontrakt danych między `ingest/` a `app/` (patrz `AGENTS.md`). Zmiana nazwy lub typu pola wymaga zgody właścicieli obu obszarów.

| Plik | Co to jest |
|---|---|
| `aed.schema.json` | **Źródło prawdy.** Frictionless Table Schema: 41 pól, typy, ograniczenia, poziomy (`x-poziom`), grupy (`x-grupa`). |
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

## Kto za co odpowiada (v0.2)

Dystrybutor (np. Centrum Ratownictwa) potwierdza, że AED jest w danym miejscu; właściciel odpowiada za stan techniczny. Każda rola ma w rekordzie komplet „kto / kiedy / jak”:

| Rola | Kto | Kiedy | Jak |
|---|---|---|---|
| Potwierdzenie lokalizacji | `lokalizacje_potwierdzil` | `data_weryfikacji` | `metoda_weryfikacji` (np. `dystrybutor`) |
| Stan techniczny | `odpowiedzialny_za_stan_techniczny` (puste = `dysponent_nazwa`) | `data_przegladu` | daty ważności elektrod i baterii |

Celowo bez osobnej „daty potwierdzenia lokalizacji” – to już `data_weryfikacji`; dwie daty o tym samym znaczeniu dawałyby sprzeczne rekordy.

## Plik od dysponenta a zbiór wynikowy (`id_aed`)

`aed.schema.json` opisuje **zbiór wynikowy** publikowany na dane.gov.pl. Pole z `"x-nadaje-system": true` (obecnie tylko `id_aed`) nadaje `ingest/` przy scalaniu, zgodnie z planem technicznym (decyzja Krystiana z 21.11.2026: wariant z planu):

- **plik od dysponenta** (arkusz „Dane” zapisany jako CSV, wczytywany przez `python -m ingest package --plik`) – pole zostaje puste; dysponenta i urządzenie identyfikuje para `zrodlo` + `id_zrodlowe`;
- **zbiór wynikowy** – pole wymagane i unikalne (klucz główny), stałe między odświeżeniami: `ingest/` liczy je jako UUID5 z pary `zrodlo` + `id_zrodlowe` (`ingest/normalize.py`, `stable_id`).

Plik od dysponenta sprawdza się schematem pochodnym: ten sam `aed.schema.json`, ale bez `primaryKey` i bez `required` w polach z `x-nadaje-system`; wpisana wartość w takim polu to błąd (dysponent nie nadaje identyfikatorów). Pokazują to testy w `tests/test_frictionless.py`. `ingest/` (`package --plik`) puste `id_aed` uzupełnia, a wpisanego nie odrzuca.

## Reguły biznesowe

Table Schema nie wyraża tych reguł, więc opisujemy je tutaj. Testy w `tests/` sprawdzają część z nich na przykładzie. Kolumna „W `ingest/`” mówi, czy walidator `ingest/validate.py` (albo inna część `ingest/`) sprawdza regułę dziś (22.11.2026).

| Reguła | Skutek | W `ingest/` |
|---|---|---|
| `godziny_dostepnosci` w składni `opening_hours` (OSM) albo dokładnie `nieznane` | błąd | nie |
| `dostepny_24h`: `tak` ⇔ godziny `24/7`; `nieznane` ⇔ godziny `nieznane`; w pozostałych przypadkach `nie` | błąd | tak |
| `data_przegladu` starsza niż 12 miesięcy od daty walidacji | ostrzeżenie | nie |
| `data_waznosci_elektrod` lub `data_waznosci_baterii` w przeszłości | ostrzeżenie | nie |
| Podany co najmniej jeden z: `dysponent_regon`, `dysponent_nip` | ostrzeżenie | tak |
| Poprawna suma kontrolna REGON (9 lub 14 cyfr) i NIP | błąd | nie (sprawdzana tylko długość, wzorcem ze schematu) |
| Współrzędne wewnątrz granic Polski i w gminie z `kod_teryt_gminy` | błąd / ostrzeżenie | granice Polski – tak (zakresy ze schematu); gmina – w mapie luk (punkt spoza gminy dysponenta) |
| Unikalne `id_zrodlowe` w obrębie jednego źródła | błąd | tak |
| Pole z `x-nadaje-system` (`id_aed`) wypełnione w pliku od dysponenta | błąd | nie (sprawdza `tests/test_frictionless.py`) |
| `zrodlo` – identyfikatory istniejące w `ingest/sources.toml` | błąd | nie (puste `zrodlo` w pliku dostawcy dostaje `plik-dostawcy`) |
| `telefon_kontaktowy` – tylko numer instytucji, nigdy osoby prywatnej (RODO) | weryfikacja przy imporcie | tak, przy imporcie z OSM (telefon tylko z `operator`) |
| Kod do szafki nigdy nie trafia do danych – tylko `kod_do_szafki_u_dyspozytora` = tak/nie | – | – (schemat nie ma pola na kod) |
| `dostep` = `nieznany` | ostrzeżenie | tak |
| `metoda_weryfikacji` = `dystrybutor` lub `dysponent`, a `lokalizacje_potwierdzil` puste | ostrzeżenie | tak |
| `lokalizacje_potwierdzil`, `odpowiedzialny_za_stan_techniczny` – tylko nazwy instytucji, nigdy osób (RODO) | weryfikacja przy imporcie | instrukcja dla dystrybutora (`CZYTAJ-MNIE.txt`); automatycznie – nie |

## Historia decyzji (zmiany względem pierwszej wersji planu)

Decyzje Krystiana z 21.11.2026:
1. `godziny_dostepnosci` zostaje wymagane, ale przyjmuje wartość `nieznane` – rekordy bez godzin nie są odrzucane. W konsekwencji `dostepny_24h` ma wartości `tak` / `nie` / `nieznane` (zamiast tak/nie).
2. Reguła dat: ostrzeżenie, gdy przegląd jest starszy niż 12 miesięcy oraz gdy elektrody lub bateria straciły ważność (zamiast „data przeglądu nie w przeszłości”).
3. `id_aed`: przyjęta propozycja z planu – puste w pliku od dysponenta, wymagane w zbiorze wynikowym (sekcja wyżej).
4. **v0.2 (issue #25, ustalenia z mentorem pkt 4–6):** `dostep` przyjmuje `nieznany` (ostrzeżenie zamiast odrzucenia rekordu); `metoda_weryfikacji` ma wartość `dystrybutor`; dwa nowe pola zalecane opisują dwie odpowiedzialności – zob. sekcję „Kto za co odpowiada”.
5. **`data_aktualizacji` w czasie polskim bez strefy (22.11.2026, decyzja Tymka w zastępstwie Krystiana, #61):** zapis `2026-11-21T13:00:00` zamiast `2026-11-21T12:00:00Z`. Dane tabelaryczne dane.gov.pl przyjmują tylko daty bez strefy (`DATE_BASE_FORMATS` w `portal/mcod/settings/base.py`) – plik z `Z` albo `+00:00` nie przechodził walidacji danych na portalu (test w #61). Typ pola (`datetime`) bez zmian.

Doprecyzowania techniczne: `dysponent_regon` i `dysponent_nip` to dwie osobne kolumny; rekord scalony z kilku źródeł ma w `zrodlo` identyfikatory rozdzielone `;`; `licencja` to identyfikator SPDX (np. `CC-BY-4.0`).
