# Wideo-prezentacja prototypu „Znajdź AED”

Wynik: [`presentation/wideo-prezentacja-aedane.mp4`](../../wideo-prezentacja-aedane.mp4). Film trwa 68 s, ma rozdzielczość 1920×1080 i 30 kl./s, jest bez dźwięku. Po lewej widać prawdziwe nagranie prototypu na telefonie (iPhone, 390×844 px), po prawej podpis kroku.

## Sceny

| # | Scena | Co widać |
|---|---|---|
| – | Plansza otwierająca | logotyp, „Znajdź AED – prototyp modułu dla dane.gov.pl” |
| 1 | Najpierw 112 lub 999 | przypomnienie o numerach alarmowych, „Użyj mojej lokalizacji” |
| 2 | Najbliższy AED dostępny teraz | mapa, karta najbliższego AED: 220 m w linii prostej, 280 m pieszo, 270 m samochodem |
| 3 | Wszystko w jednym dymku | adres, opis miejsca, godziny, telefon, zdjęcie szafki |
| 4 | „Wyznacz trasę” | trasa w Mapach Google (zrzut `zrzuty/obywatel-4-trasa-google.jpg`) |
| – | Wzorcowy zakres danych | przewijanie podstrony AED z pełnymi danymi |
| – | Dla każdego | legenda „Jak czytać mapę” pod mapą |
| – | Dostępność WCAG 2.2 | tryb wysokiego kontrastu czarno-żółty |
| – | Plansza końcowa | hasło „Otwarte dane. Cenne sekundy. Uratowane życie.”, zespół |

AED „Centrum Kultury Przykładowe” to rekord wzorcowy z arkusza (dane poglądowe), tak samo jak na slajdach. Film mówi o tym w stałej adnotacji. Pozostałe AED na mapie to prawdziwe dane. Zegar nagrania: wtorek 11:00, start w punkcie 52.176, 21.016. Odległości liczą na żywo serwery tras FOSSGIS.

## Jak nagrać ponownie

Potrzebne są: Node.js z Playwright (Chromium), Python z Pillow, `rsvg-convert`, krój Inter i `ffmpeg`.

```bash
cp -r app /tmp/app-demo && node presentation/narzedzia/rekord_wzorcowy.js /tmp/app-demo
(cd /tmp/app-demo && python -m http.server 8770 &)
node presentation/narzedzia/wideo/nagranie.js /tmp/aedane-wideo     # klatki ze strony (ok. 1 min)
python presentation/narzedzia/wideo/tla.py /tmp/aedane-wideo        # tła scen z podpisami
python presentation/narzedzia/wideo/montaz.py /tmp/aedane-wideo     # montaż → presentation/wideo-prezentacja-aedane.mp4
```

- **Nagranie:** strona jest filmowana zrzutami ekranu przeglądarki (CDP screencast, JPEG 92). Długie oczekiwanie na trasy jest skrócone do najwyżej 1,2 s między klatkami.
- **Montaż:** każda scena jest osobnym plikiem MP4 (H.264, CRF 18). Pliki są łączone bez ponownego kodowania.
