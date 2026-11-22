"""Generuje branding/zrodla/ksiega-znaku.html (źródło księgi znaku) z plików SVG w branding/.

Uruchomienie (z katalogu głównego repo):
    python branding/narzedzia/ksiega.py
PDF: otwórz HTML w Chrome i „Drukuj → Zapisz jako PDF” (A4 poziomo, z grafiką tła)
albo użyj Playwright: page.pdf(width="297mm", height="210mm", print_background=True).
Krój Montserrat (SIL OFL) musi być zainstalowany w systemie, inaczej użyty zostanie Arial.
"""
import re
from pathlib import Path
B = Path(__file__).resolve().parents[1]
logo = (B / 'logotyp-aedane.svg').read_text()
ikona = (B / 'ikona-aedane.svg').read_text()
GREEN, NAVY = '#00965E', '#1B266B'
# obrys treści logotypu w pliku 2380×795 (zmierzony): x 147–2238, y 144–654; moduł x = bok kwadratu = 52 px
CROP = '147 144 2092 511'

def inner(svg):
    return re.search(r'<svg[^>]*>(.*)</svg>', svg, re.S).group(1).replace('<title>AEDane</title>', '')

LOGO_IN, IKONA_IN = inner(logo), inner(ikona)

def logo_svg(fill=None, cls='', style='', vb=CROP, extra=''):
    body = LOGO_IN
    if fill:
        body = body.replace(f'fill="{GREEN}"', f'fill="{fill}"').replace(f'fill="{NAVY}"', f'fill="{fill}"')
    return f'<svg class="{cls}" style="{style}" viewBox="{vb}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Logotyp AEDane">{extra}{body}</svg>'

def ikona_svg(fill=None, cls='', style=''):
    body = IKONA_IN if not fill else IKONA_IN.replace(f'fill="{GREEN}"', f'fill="{fill}"')
    return f'<svg class="{cls}" style="{style}" viewBox="140 225 745 590" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Znak AEDane">{body}</svg>'

X = '<svg class="x" viewBox="0 0 100 100"><path d="M8 8 92 92M92 8 8 92" stroke="#D0021B" stroke-width="7"/></svg>'

def bad(content, caption, bg='#fff'):
    return f'<figure class="bad"><div class="bad__box" style="background:{bg}">{content}{X}</div><figcaption>{caption}</figcaption></figure>'

# pole ochronne: obrys + 2x (x = 52 jednostek) – rysowane w układzie logotypu
x = 52
clear = (f'<svg class="clear" viewBox="{147-2*x-10} {144-2*x-10} {2092+4*x+20} {511+4*x+20}" xmlns="http://www.w3.org/2000/svg">'
         f'<rect x="{147-2*x}" y="{144-2*x}" width="{2092+4*x}" height="{511+4*x}" fill="#E8F5EF" stroke="{GREEN}" stroke-width="4" stroke-dasharray="18 12"/>'
         f'<rect x="147" y="144" width="2092" height="511" fill="#fff" stroke="#9AA" stroke-width="3"/>'
         f'{LOGO_IN}'
         f'<rect x="279" y="{144-2*x}" width="52" height="{2*x}" fill="{NAVY}" opacity=".25"/>'
         f'<text x="340" y="{144-x+12}" font-size="40" fill="{NAVY}" font-family="Montserrat, sans-serif">2x</text>'
         f'<rect x="279" y="144" width="52" height="52" fill="none" stroke="#D0021B" stroke-width="5"/>'
         f'<text x="340" y="185" font-size="40" fill="#D0021B" font-family="Montserrat, sans-serif">x</text>'
         '</svg>')

html = f'''<!doctype html><html lang="pl"><head><meta charset="utf-8"><title>AEDane – księga znaku</title>
<style>
@font-face {{ font-family: 'MontserratVar'; font-weight: 100 900; src: local('Montserrat'), url('file:///usr/share/fonts/truetype/google-fonts/ofl/montserrat/Montserrat%5Bwght%5D.ttf') format('truetype'); }}
@page {{ size: A4 landscape; margin: 0; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; font-family: MontserratVar, Arial, sans-serif; font-weight: 400; color: #1d1d1b; }}
.page {{ width: 297mm; height: 210mm; padding: 18mm 20mm 14mm; page-break-after: always; position: relative; overflow: hidden; }}
.page:last-child {{ page-break-after: auto; }}
.num {{ position: absolute; right: 20mm; bottom: 9mm; font-size: 9pt; color: #6b6b6b; }}
.brandline {{ position: absolute; left: 20mm; bottom: 9mm; font-size: 9pt; color: #6b6b6b; }}
h1 {{ font-size: 26pt; margin: 0 0 8mm; color: {NAVY}; }}
h2 {{ font-size: 13pt; margin: 0 0 3mm; color: {NAVY}; }}
p, li {{ font-size: 11pt; line-height: 1.5; }}
.cover {{ display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center; }}
.cover .logo {{ width: 190mm; }}
.cover .claim {{ font-size: 24pt; font-weight: 700; color: {GREEN}; margin: 12mm 0 3mm; }}
.cover .sub {{ font-size: 13pt; color: {NAVY}; margin: 0; }}
.cover .doc {{ position: absolute; top: 14mm; left: 20mm; font-size: 10pt; letter-spacing: .1em; text-transform: uppercase; color: #6b6b6b; }}
.cols {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14mm; align-items: start; }}
.variants {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 8mm; }}
.variants figure, .bad {{ margin: 0; }}
.tile {{ height: 48mm; display: flex; align-items: center; justify-content: center; padding: 8mm; border: .3mm solid #d8d8d8; }}
.tile svg {{ width: 100%; max-height: 100%; }}
.tile.icon svg {{ width: auto; height: 34mm; }}
figcaption {{ font-size: 9.5pt; margin-top: 2mm; color: #444; }}
.sw {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 8mm; }}
.sw__chip {{ height: 40mm; border: .3mm solid #d8d8d8; }}
.sw table {{ font-size: 9.5pt; margin-top: 3mm; border-collapse: collapse; }}
.sw td {{ padding: .6mm 3mm .6mm 0; }}
.clear {{ width: 100%; }}
.sizes {{ display: flex; gap: 14mm; align-items: flex-end; margin-top: 4mm; }}
.sizes figure {{ margin: 0; }}
.bads {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 6mm; }}
.bad__box {{ position: relative; height: 34mm; display: flex; align-items: center; justify-content: center; padding: 4mm; border: .3mm solid #d8d8d8; overflow: hidden; }}
.bad__box > svg:not(.x) {{ width: 100%; max-height: 100%; }}
.x {{ position: absolute; top: 2mm; right: 2mm; width: 8mm; height: 8mm; }}
.note {{ font-size: 9.5pt; color: #555; }}
</style></head><body>

<section class="page cover">
  <div class="doc">Księga znaku · akcja dla dysponentów danych o AED · dane.gov.pl</div>
  {logo_svg(cls='logo')}
  <p class="claim">Otwarte dane. Cenne sekundy. Uratowane życie.</p>
  <p class="sub">Udostępnij dane o swoim defibrylatorze na dane.gov.pl.</p>
  <span class="num">1</span>
</section>

<section class="page">
  <h1>Koncepcja</h1>
  <div class="cols">
    <div>
      <p>Serce zbudowane z kwadratowych pikseli to dane: każdy kwadrat to jeden rekord o defibrylatorze, a razem tworzą znak życia. Błyskawica przecinająca serce nawiązuje do symbolu AED i impulsu, który przywraca rytm serca. Luźne piksele na brzegach to dane wciąż rozproszone – akcja zaprasza ich dysponentów, by dołączyli do wspólnego zbioru na dane.gov.pl. Nazwa AEDane łączy „AED” i „dane”, a czytana na głos brzmi jak pytanie „A dane?” – zadawane każdemu, kto ma defibrylator.</p>
      <h2>Hasło akcji</h2>
      <p><strong>Otwarte dane. Cenne sekundy. Uratowane życie.</strong><br>Udostępnij dane o swoim defibrylatorze na dane.gov.pl.</p>
      <h2>Do kogo</h2>
      <p>Do dysponentów AED: gmin, szpitali, uczelni, szkół, firm i dystrybutorów urządzeń. Logotyp oznacza zachętę do publikacji danych w jednolitym, wzorcowym zakresie – nie oznacza samego urządzenia AED (do tego służy znak bezpieczeństwa wg ISO 7010).</p>
    </div>
    <div class="tile icon" style="height:120mm">{ikona_svg()}</div>
  </div>
  <span class="brandline">AEDane · księga znaku</span><span class="num">2</span>
</section>

<section class="page">
  <h1>Wersje znaku</h1>
  <div class="variants">
    <figure><div class="tile">{logo_svg()}</div><figcaption><strong>Podstawowa</strong> – na białym lub jasnym tle. Używaj zawsze, gdy to możliwe.</figcaption></figure>
    <figure><div class="tile" style="background:{NAVY}">{logo_svg(fill='#FFFFFF')}</div><figcaption><strong>Odwrócona</strong> – cały znak biały na granatowym lub innym ciemnym tle.</figcaption></figure>
    <figure><div class="tile">{logo_svg(fill=NAVY)}</div><figcaption><strong>Jednobarwna</strong> – granatowa, gdy dostępny jest tylko jeden kolor (np. pieczątka, grawer).</figcaption></figure>
    <figure><div class="tile icon">{ikona_svg()}</div><figcaption><strong>Sygnet</strong> – sam znak serca, gdy miejsca jest mało (ikona, awatar, favicon).</figcaption></figure>
    <figure><div class="tile icon" style="background:{GREEN}">{ikona_svg(fill='#FFFFFF')}</div><figcaption><strong>Sygnet odwrócony</strong> – biały na zielonym.</figcaption></figure>
    <figure><div class="tile icon">{ikona_svg(fill=NAVY)}</div><figcaption><strong>Sygnet jednobarwny</strong> – granatowy.</figcaption></figure>
  </div>
  <span class="brandline">AEDane · księga znaku</span><span class="num">3</span>
</section>

<section class="page">
  <h1>Kolorystyka</h1>
  <div class="sw">
    <div><div class="sw__chip" style="background:{GREEN}"></div><h2 style="margin-top:3mm">Zieleń AED</h2>
      <table><tr><td>HEX</td><td>#00965E</td></tr><tr><td>RGB</td><td>0 150 94</td></tr><tr><td>CMYK*</td><td>100 0 37 41</td></tr></table>
      <p class="note">Sygnet, „AED” w napisie. Nawiązuje do zieleni znaku bezpieczeństwa AED.</p></div>
    <div><div class="sw__chip" style="background:{NAVY}"></div><h2 style="margin-top:3mm">Granat</h2>
      <table><tr><td>HEX</td><td>#1B266B</td></tr><tr><td>RGB</td><td>27 38 107</td></tr><tr><td>CMYK*</td><td>75 64 0 58</td></tr></table>
      <p class="note">„ane” w napisie, linia podziału. Barwa instytucji i zaufania.</p></div>
    <div><div class="sw__chip" style="background:#FFFFFF"></div><h2 style="margin-top:3mm">Biel</h2>
      <table><tr><td>HEX</td><td>#FFFFFF</td></tr><tr><td>RGB</td><td>255 255 255</td></tr><tr><td>CMYK</td><td>0 0 0 0</td></tr></table>
      <p class="note">Tło wersji podstawowej, znak w wersjach odwróconych.</p></div>
  </div>
  <p class="note" style="margin-top:6mm">* Wartości CMYK przeliczone z RGB – przed drukiem do potwierdzenia w drukarni (profil ICC, ewentualnie dobór Pantone).<br>
  Dostępność (WCAG 2.2): granat na białym 13,7:1 – można nim pisać także drobny tekst. Zieleń na białym 3,8:1 – wystarcza dla grafiki i dużego tekstu (≥ 18 pt lub 14 pt pogrubione), nie dla drobnego tekstu.</p>
  <span class="brandline">AEDane · księga znaku</span><span class="num">4</span>
</section>

<section class="page">
  <h1>Pole ochronne i minimalna wielkość</h1>
  <div class="cols" style="grid-template-columns:1.35fr .9fr">
    <div>{clear}
      <p class="note">Moduł <strong>x</strong> = bok jednego kwadratu sygnetu. Wokół znaku zostaw pole ochronne <strong>2x</strong> z każdej strony – nie umieszczaj w nim tekstu, krawędzi, innych logotypów ani elementów grafiki.</p></div>
    <div>
      <h2>Minimalna wielkość</h2>
      <div class="sizes">
        <figure>{logo_svg(style='width:40mm')}<figcaption>Logotyp: 40 mm (druk) / 160 px (ekran) szerokości znaku</figcaption></figure>
        <figure>{ikona_svg(style='height:12mm')}<figcaption>Sygnet: 12 mm / 48 px</figcaption></figure>
      </div>
      <p class="note">Poniżej tych rozmiarów błyskawica i pojedyncze piksele przestają być czytelne. W mniejszych miejscach (np. favicon 16–32 px) używaj samego sygnetu i sprawdź czytelność.</p>
    </div>
  </div>
  <span class="brandline">AEDane · księga znaku</span><span class="num">5</span>
</section>

<section class="page">
  <h1>Niedozwolone użycie</h1>
  <div class="bads">
    {bad(logo_svg(style="transform:scaleX(1.45)"), 'Nie rozciągaj i nie zmieniaj proporcji.')}
    {bad(logo_svg(style="transform:rotate(-12deg)"), 'Nie obracaj znaku.')}
    {bad(logo_svg().replace(GREEN, '#E4572E').replace(NAVY, '#F2A541'), 'Nie zmieniaj kolorów.')}
    {bad(logo_svg(style="filter:drop-shadow(6px 6px 3px rgba(0,0,0,.55))"), 'Nie dodawaj cieni, obrysów ani efektów.')}
    {bad(logo_svg(), 'Nie umieszczaj wersji podstawowej na tle o słabym kontraście.', bg=GREEN)}
    {bad(logo_svg(vb='1000 144 1238 511'), 'Nie używaj samego napisu bez sygnetu ani nie zmieniaj kolejności elementów.')}
    {bad('<svg viewBox="0 0 300 80"><text x="10" y="55" font-size="52" font-family="Georgia, serif" fill="#00965E">AED<tspan fill="#1B266B">ane</tspan></text></svg>', 'Nie przepisuj napisu innym krojem pisma.')}
    {bad(ikona_svg(style="height:26mm"), 'Nie używaj sygnetu jako znaku AED na urządzeniu lub szafce – tam obowiązuje znak bezpieczeństwa ISO 7010 (E010).', bg='#fff')}
  </div>
  <span class="brandline">AEDane · księga znaku</span><span class="num">6</span>
</section>

<section class="page">
  <h1>Pliki i zastosowanie</h1>
  <div class="cols">
    <div>
      <h2>Pliki w repozytorium (katalog branding/)</h2>
      <ul>
        <li>logotyp-aedane.svg · .png · .jpg · .pdf – logotyp poziomy</li>
        <li>ikona-aedane.svg, ikona-aedane-1024.png · .jpg · .pdf – sygnet</li>
        <li>ksiega-znaku-aedane.pdf – ta księga; źródło: zrodla/ksiega-znaku.html</li>
      </ul>
      <p class="note">SVG odtworzono wektorowo z plików PNG (zgodność ok. 98% pikseli). Jeśli istnieje plik źródłowy z programu graficznego, wyeksportowany z niego SVG ma pierwszeństwo.</p>
    </div>
    <div>
      <h2>Przykłady zastosowania</h2>
      <ul>
        <li>baner w module „Znajdź AED” przy danych bez dysponenta: „Jesteś dysponentem AED? Udostępnij dane na dane.gov.pl”,</li>
        <li>pakiet dla dysponenta (szablon XLSX, instrukcja publikacji),</li>
        <li>plakaty i posty w mediach społecznościowych gmin i szpitali,</li>
        <li>naklejka „Dane tego AED są na dane.gov.pl” przy szafce – obok, nie zamiast znaku ISO 7010.</li>
      </ul>
    </div>
  </div>
  <span class="brandline">AEDane · księga znaku</span><span class="num">7</span>
</section>
</body></html>'''
(B / 'zrodla' / 'ksiega-znaku.html').write_text(html, encoding='utf-8')
print('ok', len(html))
