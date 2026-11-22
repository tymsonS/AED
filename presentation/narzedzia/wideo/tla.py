# Tła scen 1920×1080: ramka telefonu po lewej, podpis po prawej (Inter), logotyp AEDane.
# Użycie: python tla.py [katalog-roboczy]  (domyślnie /tmp/aedane-wideo). Wymaga: Pillow, rsvg-convert, krój Inter.
from PIL import Image, ImageDraw, ImageFont
import pathlib, subprocess, sys
D = sys.argv[1] if len(sys.argv) > 1 else '/tmp/aedane-wideo'
REPO = pathlib.Path(__file__).resolve().parents[3]
pathlib.Path(D).mkdir(parents=True, exist_ok=True)
W, H = 1920, 1080
BG = (244, 246, 248); NAVY = (27, 38, 107); GREEN = (0, 150, 94); TXT = (40, 44, 52); MUTED = (95, 102, 115)
F = '/usr/share/fonts/opentype/inter/Inter-%s.otf'
f = lambda w, s: ImageFont.truetype(F % w, s)
subprocess.run(['rsvg-convert', '-h', '120', str(REPO / 'branding/logotyp-aedane.svg'), '-o', f'{D}/logo120.png'], check=True)
subprocess.run(['rsvg-convert', '-h', '200', str(REPO / 'branding/logotyp-aedane.svg'), '-o', f'{D}/logo200.png'], check=True)
LOGO = Image.open(f'{D}/logo120.png').convert('RGBA')
# telefon: ekran 434×940 (780×1688 przeskalowane), ramka 14 px
PX, PY, PW, PH = 300, 70, 434, 940
NOTE = 'AED „Centrum Kultury Przykładowe” to rekord wzorcowy z arkusza (dane poglądowe). Pozostałe AED na mapie – prawdziwe dane.'

def wrap(d, text, font, width):
    out, line = [], ''
    for w in text.split():
        t = (line + ' ' + w).strip()
        if d.textlength(t, font=font) <= width: line = t
        else: out.append(line); line = w
    out.append(line); return out

def scene(name, num, title, body, note=True):
    im = Image.new('RGB', (W, H), BG); d = ImageDraw.Draw(im)
    # ramka telefonu
    d.rounded_rectangle((PX - 14, PY - 14, PX + PW + 14, PY + PH + 14), radius=58, fill=(22, 24, 30))
    d.rounded_rectangle((PX, PY, PX + PW, PY + PH), radius=44, fill=(255, 255, 255))
    x = 880; y = 300
    d.text((x, y), num, font=f('Bold', 30), fill=GREEN); y += 62
    for l in wrap(d, title, f('Bold', 64), 900): d.text((x, y), l, font=f('Bold', 64), fill=NAVY); y += 80
    y += 26
    for l in wrap(d, body, f('Regular', 36), 880): d.text((x, y), l, font=f('Regular', 36), fill=TXT); y += 54
    im.paste(LOGO, (W - LOGO.width - 70, 60), LOGO)
    if note:
        for i, l in enumerate(wrap(d, NOTE, f('Regular', 22), 900)):
            d.text((x, H - 120 + i * 32), l, font=f('Regular', 22), fill=MUTED)
    im.save(f'{D}/bg_{name}.png')

def card(name, lines):
    im = Image.new('RGB', (W, H), BG); d = ImageDraw.Draw(im)
    L = Image.open(f'{D}/logo200.png').convert('RGBA')
    im.paste(L, ((W - L.width) // 2, 300), L)
    y = 580
    for text, font, col in lines:
        tw = d.textlength(text, font=font); d.text(((W - tw) / 2, y), text, font=font, fill=col); y += font.size + 24
    im.save(f'{D}/bg_{name}.png')

scene('s1', 'KROK 1', 'Najpierw 112 lub 999', 'Strona od razu przypomina o wezwaniu pomocy. Potem jedno stuknięcie: „Użyj mojej lokalizacji” – albo wpisany adres.')
scene('s2', 'KROK 2', 'Najbliższy AED dostępny teraz', 'Mapa ponad 18 tys. AED. Karta pokazuje najbliższy czynny defibrylator i odległość: w linii prostej, pieszo i samochodem.')
scene('s3', 'KROK 3', 'Wszystko w jednym dymku', 'Adres, opis miejsca, godziny, telefon i zdjęcie szafki. Etykieta „Zweryfikowany” mówi, że za dane odpowiada instytucja.')
scene('g', 'KROK 4', '„Wyznacz trasę” – i w drogę', 'Jedno stuknięcie otwiera trasę do AED w Mapach Google, na telefonie od razu w aplikacji.')
scene('s4', 'WZORCOWY ZAKRES DANYCH', 'Tak wygląda wzorcowo opisany AED', 'Podstrona z pełnymi danymi: kiedy i dla kogo jest dostępny, gdzie dokładnie wisi, kto za niego odpowiada i kto go zweryfikował.')
scene('s5', 'DLA KAŻDEGO', 'Mapa czytelna bez instrukcji', 'Legenda prostym językiem: kolor mówi, czy AED jest dostępny teraz, a znaczek ✓ – czy dane potwierdziła instytucja, czy społeczność.')
scene('s6', 'DOSTĘPNOŚĆ WCAG 2.2', 'Tryby wysokiego kontrastu', 'Te same przełączniki co na dane.gov.pl. Wszystkie teksty mają kontrast co najmniej 4,5:1 – także dla osób słabowidzących.')
card('intro', [('Znajdź AED', f('Bold', 72), NAVY),
               ('Prototyp modułu dla dane.gov.pl · Misja AED – Dane na ratunek · HackNation 2026', f('Regular', 32), TXT)])
card('outro', [('Otwarte dane. Cenne sekundy. Uratowane życie.', f('Bold', 56), NAVY),
               ('Udostępnij dane o swoim defibrylatorze na dane.gov.pl.', f('Regular', 34), GREEN),
               ('Krystian Poprawa · Mikołaj Rochowiak · Tymoteusz Szymański · Jakub Stachowski · Paweł Prandzioch · Jan Rodź', f('Regular', 24), MUTED)])
# maska zaokrąglonych rogów ekranu
m = Image.new('L', (PW, PH), 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, PW - 1, PH - 1), radius=44, fill=255); m.save(f'{D}/mask.png')
