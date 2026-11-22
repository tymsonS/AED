# app/ – prototyp „Znajdź AED”

Obszar Krystiana (patrz `AGENTS.md`). Statyczna strona: przycisk **Znajdź AED** odczytuje lokalizację, pod spodem pokazuje mapę ze wszystkimi AED i wyróżnia najbliższy **dostępny teraz**. „Wyznacz trasę pieszo” otwiera Mapy Google (na telefonie – aplikację). Wygląd i układ odtworzone wg kodu frontendu dane.gov.pl: pasek górny, przełączniki kontrastu A/A/A/A i wielkości tekstu A–A+++, PL/EN, Zarejestruj się / Zaloguj się, pełne menu portalu (z „Więcej”), okruszki „Jesteś w sekcji”, panel „Filtry”, karty wyników, czterokolumnowa stopka z CMS portalu. Linki menu i stopki prowadzą do prawdziwych podstron dane.gov.pl – strona działa jak dodatkowa podstrona portalu. Mapa ze wszystkimi AED jest widoczna od wejścia na stronę.

**Bez znaków państwowych:** zamiast godła, „gov.pl”, „Serwis Rzeczypospolitej Polskiej”, logo Otwarte Dane, logo UE i „Mój Gov” – znak i opis modułu (strona hostowana poza portalem nie może udawać serwisu państwowego). Po wpięciu w dane.gov.pl moduł dostaje nagłówek portalu; podmiana to kilka linii w `index.html`.

**Licencja:** kod portalu jest na GPL v3. Krystian dopuścił kopiowanie jego plików; jeśli to zrobimy, `app/` musi być udostępniony na GPL v3 (decyzja zespołu, także w kontekście przeniesienia praw na MC z regulaminu). Obecna wersja nie zawiera skopiowanych plików portalu – tylko odtworzone wartości (kolory, wymiary) i treść linków.

## Uruchomienie

Bez instalacji i bez budowania:

```bash
cd app && python -m http.server 8000   # potem http://localhost:8000
```

Bez Pythona (Windows): `npx --yes http-server -p 8000 -c-1` (wymaga Node.js; `-c-1` wyłącza pamięć podręczną) albo dwuklik w `index.html` – wtedy zamiast lokalizacji wybierz miejscowość z listy.

Lokalizacja działa tylko w bezpiecznym kontekście (`https://` albo `http://localhost`). Po otwarciu `index.html` prosto z dysku strona działa, ale przeglądarka może odmówić lokalizacji – wtedy wybierz miejscowość z listy albo kliknij na mapie.

Pliki CSS/JS są dołączane z numerem wersji (`?v=…` w `index.html`) – po każdej zmianie stylów lub skryptów podbij go, żeby przeglądarki nie użyły starych plików z pamięci podręcznej.

Podkład mapy pobierany jest z serwerów OpenStreetMap, więc mapa wymaga internetu. Leaflet i czcionka Roboto są w `vendor/` (bez CDN).

## Znak akcji

W nagłówku logotyp akcji AEDane (195×65 px, na telefonie 180×60 px; nazwa modułu „Znajdź AED” jest w tytule strony i w menu), w obu rogach paska serwisu sygnet (serce z błyskawicą). Pliki `img/*.svg` to kopie z `branding/`; rozmiary nie mniejsze niż w księdze znaku (logotyp 160 px, sygnet 48 px), w trybie wysokiego kontrastu znak leży na białym polu.

## Wyszukiwarka (układ jak „Znajdź Paczkomat”)

Mapa na całą szerokość z pływającym panelem (na telefonie: sterowanie → mapa → wyniki):
- **Użyj mojej lokalizacji** – geolokalizacja przeglądarki (działa tylko na `https://` i `localhost`). Po odmowie strona nie może ponownie wyświetlić systemowego pytania, więc pokazuje kroki włączenia lokalizacji dla iPhone’a/iPada (Safari), Androida albo komputera i przycisk „Spróbuj ponownie” (`AedCore.geoHelp`),
- **pole adresu** – dowolne miejsce: najpierw miejscowości z naszych danych (bez sieci), potem Nominatim (OpenStreetMap), awaryjnie geokoder GUGiK (`services.gugik.gov.pl/uug`, `srid=4326`); zapytanie dopiero po zatwierdzeniu (zasady Nominatim – bez podpowiedzi przy każdym znaku). Na produkcji MC powinno użyć własnej instancji geokodera albo GUGiK,
- zakładki **Wszystkie / Dostępne teraz**, **Wyniki: N w promieniu 5 km** (okrąg na mapie), gdy pusto – najbliższy spoza promienia,
- **podpowiedzi podczas pisania – tylko AED z mapy** (jak w wyszukiwarce paczkomatów; od 2 znaków, w przeglądarce, bez sieci): szukanie po nazwie, ulicy, miejscowości, gminie (z granic PRG w `ingest/`), opisie miejsca i dysponencie, bez polskich znaków; każde wpisane słowo musi pasować; kolejność – jakość dopasowania, potem odległość od wskazanego punktu lub środka przybliżonej mapy. Wybór podpowiedzi pokazuje AED w promieniu 5 km od wybranego i otwiera jego dymek. Enter bez wybranej podpowiedzi wyszukuje wpisany adres (Nominatim, awaryjnie GUGiK). Pole działa jak combobox wg WAI-ARIA APG: strzałki, Enter, Esc, `aria-activedescendant`, komunikat dla czytnika ekranu; wpisane fragmenty są pogrubione,
- **odległość po drogach – pieszo i samochodem** (ikony własne, SVG), obok odległości w linii prostej: serwery tras FOSSGIS na danych OSM: pieszo OSRM (`routing.openstreetmap.de`, profil `foot`), samochodem Valhalla (`valhalla1.openstreetmap.de`, `auto`) – dwa serwery, więc oba tryby liczą się równolegle. Na każdy serwer jedno zapytanie naraz (OSRM odpowiada 429 na równoległe), ≥ 1,1 s między zapytaniami (zasady FOSSGIS: maks. 1/s, bez intensywnego użycia), przerwanie po 4 s (pieszo wtedy ponawiamy na serwerze Valhalla, profil `pedestrian`). Najpierw wyróżniony AED i 5 pierwszych wyników, kolejne – gdy pojawią się na ekranie (IntersectionObserver). Pamięć wyników. Gdy start lub AED leży > 75 m od drogi danego profilu (samochodem > 400 m – między blokami czy w parku droga dla aut bywa 100–300 m dalej, a do auta i tak się dochodzi) albo trasa wychodzi krótsza niż linia prosta, pokazujemy „–” zamiast mylącej liczby. Mapy Google nie są źródłem tych liczb: wymagają płatnego klucza API, a regulamin nie pozwala pokazywać ich wyników na mapie innej niż Google,
- **podstrona AED „Szczegóły”** (`aed.html`, jak strona paczkomatu): czytelny adres `aed.html?aed=aed-<miejscowość lub gmina>-<nazwa lub opis>-<kod>-<województwo>`, np. `aed-krosno-panstwowa-akademia-nauk-stosowanych-b1be591660-podkarpackie`. AED rozpoznajemy tylko po kodzie (10 znaków z `id_aed`, stały między budowaniami), więc zmiana nazwy w danych nie psuje starych linków – strona sama poprawia adres na aktualny. Treść od najważniejszej: status i dostępność teraz, nazwa, miejsce, odległość (w linii prostej, pieszo, samochodem), „Wyznacz trasę” i „Pokaż na mapie”, mini mapa; dalej „Kiedy i dla kogo” (godziny po polsku, dostęp), „Gdzie dokładnie”, „Kto odpowiada”, „Weryfikacja i źródło danych”. Punkt wyszukiwania przechodzi na podstronę przez `sessionStorage` (tylko ta karta), nie przez adres – link do AED można udostępnić bez zdradzania swojego położenia,
- **prywatność położenia:** punkt wyszukiwania nie trafia do adresu strony i nie jest nigdzie zapisywany (tylko `sessionStorage` tej karty, żeby podstrona AED znała odległość). Do serwerów tras FOSSGIS wysyłamy go zaokrąglonego do 3 miejsc po przecinku (ok. 100 m, `AedCore.roundStart`); odległość w linii prostej liczymy lokalnie z dokładnego punktu. Dokładny punkt dostają Mapy Google dopiero po kliknięciu „Wyznacz trasę”. Wpisany adres (nie położenie) wysyłamy do Nominatim/GUGiK po Enter. Opis pod mapą mówi dokładnie to samo (uwaga z review #43),
- **ograniczenie prototypu – serwery tras:** publiczne serwery FOSSGIS (limit 1 zapytanie/s, bez intensywnego użycia) wystarczają na prototyp. Przy wdrożeniu na dane.gov.pl potrzebny jest własny serwer tras (OSRM lub Valhalla na danych OSM dla Polski) – adresy są w stałych `OSRM_FOOT` i `VALHALLA` w `js/app.js` i `js/aed-detail.js`,
- **zdjęcie miejsca AED** w dymku (pod przyciskiem „Wyznacz trasę”, żeby na małym telefonie przycisk był widoczny bez przewijania; pełna szerokość) i większe na podstronie (nad mapą); gdy zdjęcia nie ma albo się nie wczyta – mały znak „Brak zdjęcia miejsca”. Pokazujemy tylko zdjęcia o znanych prawach: wgrane do OpenAEDMap – adres `/api/v1/photos/view/…` (backend przyjmuje wyłącznie CC0; `/api/v1/photos/proxy/direct/…` to pośrednik do obcych obrazków o nieznanej licencji – pomijamy go; licencję deklaruje osoba wgrywająca, serwer nie sprawdza, czy ma do zdjęcia prawa – na prototyp wystarcza) i ze zbiorów instytucji z dane.gov.pl (także po potwierdzeniu przez dystrybutora), gdy adres wskazuje plik obrazu (.jpg/.png/.webp) – ok. 1,4 tys. AED. Wspólny obrazek wielu miejsc (np. znak AED przy 21 AED z Przemyśla, review #47) odrzuca `ingest/` (#49); po stronie `app/` Przemyśl odpada też dlatego, że jego adres nie wskazuje pliku obrazu. Adresy z tagu `image` w OSM prowadzące na inne strony pomijamy (nieznana licencja i treść). Ograniczenie: zdjęcia OpenAEDMap mają do ok. 2 MB i nie ma miniatur – w dymku ładują się 1,2 s po otwarciu (żeby nie konkurowały o łącze z zapytaniami o trasę), a przy oszczędzaniu danych lub łączu 2G dopiero po stuknięciu „Pokaż zdjęcie miejsca”; przy wdrożeniu warto serwować miniatury,
- **dymek wystarcza do działania:** oprócz etykiety dostępności czytelne godziny (np. „pon.–pt. 07:00–21:30”, `AedCore.hoursText`) i opis dostępu, gdy jest ograniczony lub prywatny. Jedyny wyraźny przycisk to „Wyznacz trasę”; „Szczegóły” to zwykły link. Dysponent, zwykły opis weryfikacji („Dane społeczne – …”) i źródło są tylko na podstronie – w dymku i w karcie najbliższego AED zostaje opis tylko, gdy jest ostrzeżeniem albo potwierdzeniem dystrybutora,
- **powrót z podstrony do tego samego stanu:** „Wróć do wyszukiwarki”, „Pokaż na mapie” i przycisk „wstecz” przeglądarki prowadzą do `index.html?aed=<adres podstrony>`, a strona przywraca punkt wyszukiwania (z wpisanym tekstem), zakładkę „Wszystkie / Dostępne teraz”, wynik na liście (z dołożeniem porcji, jeśli był dalej niż 50.) i otwarty dymek tego AED; potem usuwa `?aed` z adresu. Stan jest tylko w `sessionStorage` tej karty,
- znaczniki grupowane (Leaflet.markercluster, MIT); kliknięcie wyniku przybliża mapę i otwiera dymek z trasą (Mapy Google, zakładka „Najlepsze środki transportu”).

## Dane

`data/aed-data.js` generuje `scripts/build_data.py` z lekkiego eksportu `ingest/data/out/aed-app.geojson` (PR #26; od #45 i #49 z gminą, województwem i zdjęciem). Pełny `aed.geojson` czyta tylko, gdy w lekkim pliku brakuje któregoś z tych pól (starszy `ingest/`):

```bash
python -m ingest fetch-gminy   # jednorazowo (ok. 2 min): granice gmin – bez nich punkt spoza gminy dysponenta byłby „zweryfikowany”
python -m ingest fetch all && python -m ingest build all
python app/scripts/build_data.py
```

- **18 317 AED** (dane przebudowane 22.11.2026): **49 zweryfikowanych** – zbiory instytucji z dane.gov.pl (Przemyśl, Krosno, Marki), punkt na terenie gminy dysponenta – i **18 268 niezweryfikowanych**: dane społeczne z OpenStreetMap przez OpenAEDMap (ODbL 1.0, atrybucja w stopce i na mapie) oraz 1 punkt ze zbioru Marek leżący w Krośnie (możliwy błąd w danych).
- „Zweryfikowany” = dane instytucji odpowiedzialnej za zbiór (`status_weryfikacji` z `ingest/`). Potwierdzenia lokalizacji przez dystrybutora (`lokalizacje_potwierdzil`, ustalenie z mentorami) w opublikowanych zbiorach jeszcze nie ma – gdy się pojawi, dostanie osobny znak.
- Zgodnie z ustaleniem z mentorami pokazujemy oba rodzaje razem i wyraźnie oznaczone: etykieta „Zweryfikowany” (z ✓) / „Niezweryfikowany” (obrys przerywany) na liście, w dymku i w wyróżnieniu, z opisem z `opis_weryfikacji`; na mapie zweryfikowany AED ma pinezkę z odznaką ✓ (kształt, nie tylko kolor).
- Rekordy z `ten_sam_co` (ten sam AED z OSM, który ma już rekord zweryfikowany – 43 szt.) pomijamy, żeby AED nie był na mapie dwa razy.
- **Format zwarty:** słownik tekstów + wiersze z indeksami, współrzędne ×10⁵ (ok. 1 m). Plik ma ok. 1,8 MB (ok. 0,5 MB po kompresji gzip, którą robi zwykły hosting, np. GitHub Pages); 12,6 MB GeoJSON byłoby za dużo na telefon. Rozpakowuje go `AedCore.unpack()`.
- Lista wyników dokłada pozycje po 50 („Pokaż kolejne”), pinezki są tworzone raz i tylko aktualizowane – w Warszawie w promieniu 5 km jest ponad 600 AED.
- Bez fikcyjnych rekordów przykładowych: zostają w `schema/przyklad-aed.csv` jako przykład wzorcowego zakresu; na stronie ratunkowej mogłyby mylić, a „dostępny teraz” działa już na prawdziwych danych.
- Godziny dostępności ma ok. 6,8 tys. rekordów (prawie wyłącznie z OSM); pozostałe strona uczciwie pokazuje jako „godziny nieznane”.

## Jak liczymy „dostępny teraz”

`js/aed-core.js` (bez zależności, testowany w Node):
- `status` = `nieaktywny` / `w_serwisie` albo `dostep` = `prywatny` → niedostępny,
- `godziny_dostepnosci` w składni OSM `opening_hours` – obsługiwany podzbiór: `24/7`, dni (`Mo-Fr`, `Sa,Su`, `Fr-Mo`), przedziały (`08:00-16:00`, kilka po przecinku, przez północ), `off`; późniejsza reguła nadpisuje wcześniejszą,
- **wszystko, czego parser nie rozumie (np. `PH off`, `sunrise-sunset`), daje „godziny nieznane” – nigdy „dostępny”.**

## Testy

```bash
node --test app/tests/*.test.js
```

Logika godzin i odległości, kontrola wygenerowanych danych, kontrast kolorów (WCAG 2.2 AA: tekst ≥ 4,5:1, grafika ≥ 3:1). Wszystkie muszą przechodzić.

## Dostępność (WCAG 2.2 AA)

Język `pl`, link „Przejdź do wyników”, widoczny fokus, cele ≥ 24 px (przyciski ≥ 44 px), komunikaty w `role="status"`, lista jako pełny odpowiednik mapy, informacja nie tylko kolorem (etykiety tekstowe), `prefers-reduced-motion`, układ mobile first.

**Audyt axe-core 4.14 (22.11.2026, `scripts/audyt_wcag.py`, reguły WCAG 2.0/2.1/2.2 A i AA):** strona główna (start, po lokalizacji, z dymkiem, trzy tryby kontrastu) i podstrona AED, na komputerze (1440 px) i telefonie (390 px) – 14 widoków. Do powtórzenia potrzebne są Playwright z Chromium (`pip install playwright && playwright install chromium`) i axe-core (`npm i --prefix /tmp/axe axe-core@4`); polecenia są na początku skryptu.

- **0 naruszeń poza jednym znanym wyjątkiem:** `target-size` (2.5.8) na pinezkach i grupach AED, które na mapie leżą blisko siebie. Kryterium dopuszcza wyjątek „odpowiednik”: każdy AED z mapy jest też na liście wyników, gdzie przyciski mają ≥ 44 px.
- Poprawione po audycie: mini mapa na podstronie miała `role="img"` z przyciskami w środku (`nested-interactive`) – teraz `role="region"`.
- Do ręcznego sprawdzenia axe zostawia kontrast tekstu na mapie (podkład OSM) i zgodność nazwy linku z logotypem (nazwa zaczyna się od „AEDane”, tak jak napis na logotypie). Kontrast kolorów strony sprawdza `tests/contrast.test.js`.

## Licencje komponentów

Leaflet 1.9.4 – BSD-2-Clause (`vendor/leaflet/LICENSE`), Leaflet.markercluster 1.5.3 – MIT (`vendor/markercluster/LICENSE`), Roboto – SIL OFL 1.1 (`vendor/roboto/LICENSE`), podkład © autorzy OpenStreetMap (ODbL). Atrybucja zbiorów z dane.gov.pl (CC0 / CC BY 4.0) w stopce strony.
