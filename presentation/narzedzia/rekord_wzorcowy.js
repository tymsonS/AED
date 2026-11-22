// Dopisuje rekord przykładowy z arkusza wzorcowego (schema/, arkusz „Przykład”) do KOPII danych app/
// – tylko do zrzutu na slajd „Wzorcowy zakres danych”. Nie uruchamiać na app/ w repozytorium.
// Użycie: cp -r app /tmp/app-demo && node presentation/narzedzia/rekord_wzorcowy.js /tmp/app-demo
const fs = require('fs');
const path = require('path');
const dir = process.argv[2];
if (!dir || path.resolve(dir) === path.resolve(__dirname, '../../app')) {
  console.error('Podaj katalog KOPII app/, nie app/ z repozytorium.');
  process.exit(1);
}
global.window = {};
require(path.resolve(dir, 'data/aed-data.js'));
const d = window.AED_DATA;
const rec = {
  status_weryfikacji: 'zweryfikowany', zrodlo: 'plik-dostawcy', licencja: 'CC-BY-4.0',
  opis_weryfikacji: 'Dane instytucji: Centrum Kultury Przykładowe. Lokalizację potwierdził dysponent 10.11.2026.',
  status: 'aktywny', godziny_dostepnosci: '24/7', dostep: 'publiczny',
  opis_lokalizacji: 'Na zewnątrz, przy wejściu głównym, szafka na ścianie po prawej',
  nazwa_obiektu: 'Centrum Kultury Przykładowe', dysponent_nazwa: 'Centrum Kultury Przykładowe',
  telefon_kontaktowy: '+48221234567', gmina: 'Warszawa', wojewodztwo: 'mazowieckie', miejscowosc: 'Warszawa',
  ulica: 'Aleja Lotników', numer_budynku: '16', kod_pocztowy: '02-668',
  // zdjęcie poglądowe (OpenAEDMap, CC0) – rekord przykładowy nie ma własnego zdjęcia.
  // Położenie: Al. Lotników 16 (Warszawa, Służew) – w okolicy nie ma innego AED bliżej niż ok. 450 m,
  // więc z punktu startu 52.176, 21.016 AED wzorcowy jest najbliższy, a odległości są realne.
  zdjecie_url: 'https://openaedmap.org/api/v1/photos/view/xmFQlbH_OmjBGWVaLDFHPQ.webp',
};
const idx = (v) => { let i = d.slownik.indexOf(v); if (i < 0) { d.slownik.push(v); i = d.slownik.length - 1; } return i; };
d.aed.push([Math.round(52.174 * 1e5), Math.round(21.016 * 1e5)].concat(d.pola.map((f) => idx(rec[f]))));
d.kody.push('bd767fc6fc');
fs.writeFileSync(path.resolve(dir, 'data/aed-data.js'), 'window.AED_DATA = ' + JSON.stringify(d) + ';\n');
console.log('Dopisano rekord: aed.html?aed=aed-warszawa-centrum-kultury-przykladowe-bd767fc6fc-mazowieckie');
