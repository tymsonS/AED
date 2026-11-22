# Branding akcji „AEDane”

Logotyp akcji, która zachęca dysponentów AED (gminy, szpitale, uczelnie, firmy, dystrybutorów) do udostępniania danych o defibrylatorach na dane.gov.pl. Według ustaleń z mentorami (`docs/plan-techniczny.md`, punkt 2) znak służy akcji skierowanej do dostawców danych, a nie samemu wystąpieniu.

**Hasło akcji:** „Otwarte dane. Cenne sekundy. Uratowane życie.”, z podtytułem „Udostępnij dane o swoim defibrylatorze na dane.gov.pl.”

## Pliki

| Plik | Co to jest |
|---|---|
| `logotyp-aedane.png` | logotyp główny, poziomy: sygnet (serce z pikseli z błyskawicą) + napis „AEDane”, 2380×795 px – plik źródłowy, wygenerowany w Gemini 4 Hydrogen na polecenie zespołu |
| `logotyp-aedane.svg` | to samo, wektorowo (format otwarty) |
| `logotyp-aedane.jpg`, `.pdf` | to samo, JPG na białym tle i PDF (300 dpi) |
| `ikona-aedane-1024.png` | sam sygnet, 1024×1024 px – plik źródłowy, wygenerowany w Gemini 4 Hydrogen na polecenie zespołu |
| `ikona-aedane.svg` | sygnet wektorowo |
| `ikona-aedane-1024.jpg`, `.pdf` | sygnet jako JPG i PDF |
| `ksiega-znaku-aedane.pdf` | **księga znaku**: koncepcja i hasło, wersje znaku, kolorystyka, pole ochronne, minimalna wielkość, niedozwolone użycie, pliki i zastosowanie |
| `zrodla/ksiega-znaku.html` | źródło księgi znaku do edycji, generowane przez `narzedzia/ksiega.py` |
| `narzedzia/wektoryzacja.py` | odtworzenie SVG z PNG (potrace) |

- JPG i PDF powstały z PNG przez zmianę formatu (Pillow), bez zmian w samym znaku.
- SVG odtworzono z PNG obrysem wektorowym. Po wyrenderowaniu zgadza się z PNG w ok. 98% pikseli znaku, a różnice to wygładzone krawędzie. Jeśli istnieje plik źródłowy z programu graficznego, wyeksportowany z niego SVG ma pierwszeństwo – wtedy podmień SVG i przebuduj księgę.

## Najważniejsze zasady (szczegóły w księdze)

| | |
|---|---|
| Krój pisma księgi znaku | Montserrat (SIL OFL 1.1). Napis „AEDane” jest częścią pliku logotypu – nie składaj go od nowa żadnym krojem |
| Kolory | zieleń `#00965E` (RGB 0 150 94), granat `#1B266B` (RGB 27 38 107), biel. CMYK w księdze jest przeliczony z RGB i wymaga potwierdzenia w drukarni |
| Pole ochronne | 2x z każdej strony, gdzie x to bok jednego kwadratu sygnetu |
| Minimalna wielkość | logotyp 40 mm / 160 px szerokości, sygnet 12 mm / 48 px |
| Kontrast (WCAG 2.2) | granat na białym 13,7:1, zieleń na białym 3,8:1 – zieleń nadaje się tylko do grafiki i dużego tekstu |
| Nie wolno | rozciągać, obracać, zmieniać kolorów, dodawać efektów, kłaść na tło o słabym kontraście, używać samego napisu, przepisywać innym krojem, używać zamiast znaku AED ISO 7010 na urządzeniu |

## Wymagania formalne (`docs/zadanie-misja-aed.md` pkt 2 i 4)

- logotyp: .jpg, .png, .pdf i format otwarty (.svg)
- księga znaku .pdf: kolorystyka, pole ochronne, minimalna wielkość, niedozwolone użycie, opis koncepcji (4 zdania)
- hasło akcji
