# Analiza kodu portalu dane.gov.pl pod kątem zbioru AED

> Przegląd kodu źródłowego backendu portalu ([dane.gov.pl/source-code](https://dane.gov.pl/source-code/), `backend_latest.zip`, wersja 2.63.0 z 28.10.2026), wykonany na radę mentorów („zaglądajcie w kod źródłowy portalu”). Ścieżki w nawiasach wskazują pliki w tym archiwum.

**Wniosek:** dostawca może zasilać portal automatycznie plikiem XML według schematu XSD portalu, a nasz zestaw może ten plik generować. Portal nie dopuszcza jednak licencji ODbL, więc danych z OpenStreetMap nie da się opublikować jako zbioru dostawcy w obecnej postaci.

## 1. Jak dane trafiają na portal

| Sposób | Jak działa | Dla kogo |
| --- | --- | --- |
| Ręcznie | Dostawca dodaje zbiór i zasoby w panelu | Mała gmina, jednorazowo |
| Harwester XML | Portal cyklicznie pobiera plik XML z adresu dostawcy i aktualizuje zbiory | Dostawca, który chce aktualizacji bez pracy ręcznej |
| Harwester CKAN | Import z katalogu CKAN | Instytucje z własnym portalem CKAN |
| Harwester DCAT-AP | Zapytanie SPARQL do katalogu dostawcy (RDF/XML, profil DCAT-AP-PL) | Duże katalogi danych |

Źródło harwestera (`DataSource`) jest obiektem w panelu administracyjnym portalu, z częstotliwością pobierania co 1, 7, 30 lub 90 dni (`mcod/harvester/models.py`, `mcod/core/choices.py`). Konfiguruje je więc administrator portalu na wniosek dostawcy, a nie sam dostawca.

## 2. Harwester XML – wymagania (schemat 1.13)

Wymagania z `mcod/harvester/utils.py` i `data/harvester/xml_import_otwarte_dane_1_13.xsd`:

- **Wersja schematu:** element główny `datasets` w przestrzeni nazw `urn:otwarte-dane:harvester:1.13`. Portal odczytuje z niej wersję i waliduje plik względem odpowiedniego XSD. Plik niezgodny ze schematem jest odrzucany.
- **Adres pliku:** URL kończący się na `.xml`, bez spacji w nazwie, z nagłówkiem `Content-Type` `text/xml` albo `application/xml`.
- **Suma kontrolna:** obok pliku musi leżeć plik `.md5` z jego hashem, np. `aed.xml` + `aed.md5`. Po nim portal rozpoznaje, czy plik się zmienił.

Pola zbioru (`dataset`):

| Pole | Wymagane | Ograniczenia | Propozycja dla AED |
| --- | --- | --- | --- |
| `extIdent` | tak | do 36 znaków | stały id zbioru u dostawcy, np. `aed-1861011` (TERYT gminy) |
| `title/polish` | tak | do 300 znaków | „Lokalizacje defibrylatorów AED – Gmina X” |
| `description/polish` | tak | do 1000 znaków | opis + odwołanie do wzorcowego zakresu danych |
| `updateFrequency` | tak | `daily`, `weekly`, `monthly`, `quarterly`, `everyHalfYear`, `yearly`, `irregular`, `notPlanned` | `monthly` |
| `categories/category` | tak | m.in. `HEAL` (Zdrowie), `REGI`, `GOVE` | `HEAL` |
| `tags/tag` (atrybut `lang`) | tak | `pl` / `en` | `AED`, `defibrylator`, `pierwsza pomoc` |
| `resources/resource` | tak | co najmniej jeden | CSV + GeoJSON z wzorcowym zakresem |
| `conditions/dbOrCopyrightedLicenseChosen` | nie | 7 licencji CC (patrz punkt 3) | `CC BY 4.0` albo `CC0 1.0` |
| `conditions/personalData` | nie | do 4000 znaków | „nie zawiera danych osobowych” |
| `lastUpdateDate` | nie | data i czas | data eksportu |

Pola zasobu (`resource`):

| Pole | Wymagane | Ograniczenia | Propozycja dla AED |
| --- | --- | --- | --- |
| `extIdent` | tak | do 36 znaków | `aed-1861011-csv` |
| `url` | tak | `https://…` | adres pliku CSV/GeoJSON u dostawcy |
| `title/polish`, `description/polish` | tak | 300 / 1000 znaków | |
| `availability` | nie | `local` (portal kopiuje plik) / `remote` | `local` |
| `dataDate` | nie | data | data weryfikacji danych |
| `regions/terytIdent` | nie | kod TERYT, 2–7 znaków | TERYT gminy – zbiór pojawi się w wyszukiwaniu po regionie |
| `containsProtectedData` | nie | tak/nie | `false` |

## 3. Licencje: tylko Creative Commons

Model zbioru (`mcod/datasets/models.py`) i XSD dopuszczają dokładnie 7 licencji: `CC0 1.0`, `CC BY 4.0`, `CC BY-SA 4.0`, `CC BY-NC 4.0`, `CC BY-NC-SA 4.0`, `CC BY-ND 4.0`, `CC BY-NC-ND 4.0`. W kodzie backendu nie ma ODbL.

Skutki:
- **Dane z OpenStreetMap (ODbL) nie mogą trafić na portal jako zbiór dostawcy** z poprawną licencją. Zostają naszym narzędziem roboczym: mapą luk i podpowiedzią, gdzie dostawca ma sprawdzić AED w terenie.
- **Zbiór dostawcy zawiera dane, które dostawca sam zebrał lub zweryfikował** – to on odpowiada za zbiór. Bazy danych i ich licencje są poza naszym zakresem: nie publikujemy własnej bazy, a pakiet dostawcy przyjmuje tylko licencje z listy portalu.
- **Rekomendowana licencja wzorcowa:** `CC BY 4.0` (spójna z `x-licencja-domyslna` w `schema/aed.schema.json`) albo `CC0 1.0`.

## 4. Podgląd na mapie

Portal pokazuje zasób tabelaryczny na mapie, gdy dostawca wskaże kolumny (`GEO_TYPES` w `mcod/settings/base.py`):
- **współrzędne:** długość geograficzna, szerokość geograficzna (WGS84, kolumny liczbowe) i etykieta, albo
- **adres:** miejscowość, kod pocztowy, etykieta (ulica i numer opcjonalnie).

Wzorcowy zakres danych spełnia oba warianty: `dlugosc_geo`, `szerokosc_geo`, `nazwa_obiektu` oraz `miejscowosc`, `kod_pocztowy`, `ulica`, `numer_budynku`. Współrzędne muszą być liczbami z kropką dziesiętną, bez tekstu w kolumnie. Walidator `ingest/` już to sprawdza. GeoJSON jest na liście obsługiwanych formatów.

## 5. Inne elementy portalu przydatne dla nas

- **Logowanie przez login.gov.pl** (`mcod/logingovpl`): portal ma integrację z Węzłem Krajowym, czyli Profilem Zaufanym i mObywatelem. Tożsamość dostawcy jest więc potwierdzana po stronie portalu, a nasz zestaw nie musi tego robić. Zgłoszeń od obywateli z potwierdzaniem przez Profil Zaufany nie realizujemy (decyzja po rozmowie z mentorami).
- **Zgłoszenia propozycji zbiorów** (`mcod/suggestions`, `DatasetSubmission`): użytkownicy mogą zgłaszać zapotrzebowanie na dane. Kampania może zachęcać mieszkańców do zgłaszania braku zbioru AED dla ich gminy.

## 6. Co z tego zrobiliśmy

1. **Pakiet dostawcy w `ingest/`** (`python -m ingest package`, opis w `ingest/README.md`): dla wybranej gminy tworzy zasoby CSV i GeoJSON we wzorcowym zakresie, plik harwestera `aed.xml` (schemat 1.13, kategoria `HEAL`, TERYT gminy, licencja CC; z `--wykaz-aed` schemat 1.14 z flagą wykazu AED z naszej zmiany w `portal/`) i `aed.md5`. Dostawca wystawia je pod swoim adresem i prosi administratora portalu o podłączenie źródła albo dodaje zasoby ręcznie.
2. **Walidacja XML-a względem oryginalnego XSD portalu** przed oddaniem pakietu – mocny dowód zgodności z dane.gov.pl (kryterium o wadze 30%). XSD jest na licencji GPL v3, jak cały kod portalu; cały kod portalu jest w `portal/`, a `ingest` pobiera własną kopię XSD przez `fetch-xsd`.
3. **Sprawdzone na portalu:** pakiety trzech gmin wgrane na portal uruchomiony lokalnie przechodzą walidację pliku, danych i linku bez poprawek (`portal/README-DOCKER-AED.md`, „Demo”). Wykaz zbiorczy AED na wzór DGA opisuje `analiza-wykazow-portalu.md`.

## Do wyjaśnienia przy wdrożeniu

- Czy administratorzy portalu podłączają źródła harwestera XML dla małych dostawców, np. gmin, i ile to trwa – źródło harwestera konfiguruje administrator portalu, nie sam dostawca (sekcja 1).
