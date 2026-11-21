// Testy logiki „Znajdź AED”. Uruchomienie: node --test app/tests/
'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs');
const vm = require('node:vm');

const core = require('../js/aed-core.js');

// Czas lokalny: 2026-11-23 to poniedziałek.
const MON_10 = new Date(2026, 10, 23, 10, 0);
const MON_17 = new Date(2026, 10, 23, 17, 0);
const SAT_10 = new Date(2026, 10, 28, 10, 0);
const SUN_03 = new Date(2026, 10, 29, 3, 0);

test('odległość Warszawa–Kraków ok. 252 km', () => {
  const km = core.distanceKm({ lat: 52.2297, lon: 21.0122 }, { lat: 50.0647, lon: 19.945 });
  assert.ok(km > 248 && km < 256, String(km));
});

test('formatowanie odległości', () => {
  assert.equal(core.formatDistance(0.004), '10 m');
  assert.equal(core.formatDistance(0.234), '230 m');
  assert.equal(core.formatDistance(1.25), '1,3 km');
  assert.equal(core.formatDistance(42.4), '42 km');
});

test('24/7 zawsze otwarte', () => {
  assert.deepEqual(core.openAt('24/7', SUN_03), { known: true, open: true, always: true });
});

test('nieznane i puste → brak wiedzy', () => {
  for (const v of ['nieznane', '', '   ', undefined, null]) {
    assert.deepEqual(core.openAt(v, MON_10), { known: false }, String(v));
  }
});

test('Mo-Fr 08:00-16:00', () => {
  const h = 'Mo-Fr 08:00-16:00';
  assert.deepEqual(core.openAt(h, MON_10), { known: true, open: true, until: '16:00' });
  assert.deepEqual(core.openAt(h, MON_17), { known: true, open: false });
  assert.deepEqual(core.openAt(h, SAT_10), { known: true, open: false });
});

test('kilka reguł i przedziałów, późniejsza reguła nadpisuje', () => {
  const h = 'Mo-Sa 08:00-12:00,13:00-20:00; Sa 09:00-11:00';
  assert.equal(core.openAt(h, MON_17).open, true);
  assert.equal(core.openAt(h, SAT_10).open, true);
  assert.equal(core.openAt(h, new Date(2026, 10, 28, 12, 0)).open, false);
  assert.equal(core.openAt('Mo-Su 08:00-20:00; Mo off', MON_10).open, false);
});

test('przedział przez północ', () => {
  const h = 'Sa 20:00-04:00';
  assert.deepEqual(core.openAt(h, SUN_03), { known: true, open: true, until: '04:00' });
  assert.equal(core.openAt(h, new Date(2026, 10, 28, 21, 0)).open, true);
  assert.equal(core.openAt(h, new Date(2026, 10, 29, 5, 0)).open, false);
});

test('zakres dni przez niedzielę (Fr-Mo)', () => {
  assert.equal(core.openAt('Fr-Mo 10:00-12:00', new Date(2026, 10, 29, 11, 0)).open, true);
  assert.equal(core.openAt('Fr-Mo 10:00-12:00', new Date(2026, 10, 25, 11, 0)).open, false);
});

test('nieobsługiwane zapisy → nieznane (nigdy „dostępny”)', () => {
  for (const v of ['PH off', 'Mo-Fr 08:00-16:00; PH off', 'sunrise-sunset', 'Mo-Fr', 'Jan-Mar 08:00-16:00', '8-16', '10:00-10:00']) {
    assert.deepEqual(core.openAt(v, MON_10), { known: false }, v);
  }
});

test('dostępność: status i dostęp prywatny wygrywają z godzinami', () => {
  const base = { godziny_dostepnosci: '24/7', dostep: 'publiczny', status: 'aktywny' };
  assert.equal(core.availability(base, MON_10).state, 'dostepny');
  assert.equal(core.availability({ ...base, status: 'w_serwisie' }, MON_10).state, 'niedostepny');
  assert.equal(core.availability({ ...base, status: 'nieaktywny' }, MON_10).state, 'niedostepny');
  assert.equal(core.availability({ ...base, dostep: 'prywatny' }, MON_10).state, 'niedostepny');
  assert.equal(core.availability({ ...base, godziny_dostepnosci: 'nieznane' }, MON_10).state, 'nieznany');
});

test('wyróżnienie: najbliższy dostępny teraz, nie najbliższy w ogóle', () => {
  const me = { lat: 52.0, lon: 21.0 };
  const recs = [
    { id_aed: 'blisko-zamkniety', lat: 52.001, lon: 21.0, godziny_dostepnosci: 'Mo-Fr 08:00-09:00', status: 'aktywny', dostep: 'publiczny' },
    { id_aed: 'blisko-nieznany', lat: 52.002, lon: 21.0, godziny_dostepnosci: 'nieznane', status: 'nieznany', dostep: '' },
    { id_aed: 'dalej-otwarty', lat: 52.05, lon: 21.0, godziny_dostepnosci: '24/7', status: 'aktywny', dostep: 'publiczny' },
  ];
  const r = core.rank(recs, me, MON_10);
  assert.equal(r.list[0].rec.id_aed, 'blisko-zamkniety');
  assert.equal(r.highlight.rec.id_aed, 'dalej-otwarty');
  assert.equal(r.fallback, false);
});

test('wyróżnienie bez znanych godzin: najbliższy z flagą fallback', () => {
  const me = { lat: 50.0, lon: 22.0 };
  const recs = [
    { id_aed: 'a', lat: 50.3, lon: 22.0, godziny_dostepnosci: 'nieznane' },
    { id_aed: 'b', lat: 50.1, lon: 22.0, godziny_dostepnosci: 'nieznane' },
  ];
  const r = core.rank(recs, me, MON_10);
  assert.equal(r.highlight.rec.id_aed, 'b');
  assert.equal(r.fallback, true);
  assert.equal(core.rank([], me, MON_10).highlight, null);
});

test('trasa piesza w Mapach Google', () => {
  const url = new URL(core.routeUrl({ lat: 49.689, lon: 21.77 }, { lat: 49.6912, lon: 21.7655 }));
  assert.equal(url.origin + url.pathname, 'https://www.google.com/maps/dir/');
  assert.equal(url.searchParams.get('api'), '1');
  assert.equal(url.searchParams.get('origin'), '49.689,21.77');
  assert.equal(url.searchParams.get('destination'), '49.6912,21.7655');
  assert.equal(url.searchParams.get('travelmode'), 'walking');
});

test('adres', () => {
  assert.equal(
    core.address({ ulica: 'Rynek Główny', numer_budynku: '1', kod_pocztowy: '31-042', miejscowosc: 'Kraków' }),
    'Rynek Główny 1, 31-042 Kraków',
  );
  assert.equal(core.address({ miejscowosc: 'Marki' }), 'Marki');
  assert.equal(
    core.address({ ulica: 'Kazimierza Wielkiego 4,', numer_budynku: '', kod_pocztowy: '38-400', miejscowosc: 'Krosno' }),
    'Kazimierza Wielkiego 4, 38-400 Krosno',
  );
});

test('dane strony: 50 AED z main, współrzędne w Polsce, przykłady oznaczone', () => {
  const file = path.join(__dirname, '..', 'data', 'aed-data.js');
  const ctx = { window: {} };
  vm.runInNewContext(fs.readFileSync(file, 'utf-8'), ctx);
  const data = ctx.window.AED_DATA;
  assert.equal(data.aed.length, 50);
  for (const r of data.aed) {
    assert.ok(r.lat > 49 && r.lat < 55 && r.lon > 14 && r.lon < 24.2, r.id_aed);
    assert.equal(r.przyklad, false);
    assert.ok(r.zrodlo && r.licencja && r.nazwa_obiektu, r.id_aed);
  }
  assert.ok(data.przyklady.length > 0);
  for (const r of data.przyklady) assert.equal(r.przyklad, true);
  const ids = new Set(data.aed.map((r) => r.id_aed));
  assert.equal(ids.size, data.aed.length);
  // Każde źródło użyte w rekordach ma wpis do atrybucji w stopce.
  const sources = new Set(data.zrodla.map((s) => s.id));
  for (const r of data.aed) assert.ok(sources.has(r.zrodlo), r.zrodlo);
});

test('wyniki tylko w promieniu 5 km, filtr „dostępne teraz”, najbliższy spoza promienia', () => {
  const me = { lat: 50.0, lon: 20.0 };
  const recs = [
    { id_aed: 'a', lat: 50.01, lon: 20.0, godziny_dostepnosci: 'nieznane' }, // ~1,1 km
    { id_aed: 'b', lat: 50.03, lon: 20.0, godziny_dostepnosci: '24/7', status: 'aktywny' }, // ~3,3 km
    { id_aed: 'c', lat: 50.1, lon: 20.0, godziny_dostepnosci: '24/7', status: 'aktywny' }, // ~11 km
  ];
  const ranked = core.rank(recs, me, MON_10);
  const all = core.inRadius(ranked.list, 5, false);
  assert.deepEqual(all.items.map((i) => i.rec.id_aed), ['a', 'b']);
  assert.equal(all.nearestOutside.rec.id_aed, 'c');
  const avail = core.inRadius(ranked.list, 5, true);
  assert.deepEqual(avail.items.map((i) => i.rec.id_aed), ['b']);
  const none = core.inRadius(ranked.list, 0.5, false);
  assert.equal(none.items.length, 0);
  assert.equal(none.nearestOutside.rec.id_aed, 'a');
});

test('geokodowanie: Nominatim, GUGiK, miejscowość z danych', () => {
  assert.deepEqual(
    core.parseNominatim([{ lat: '52.3363752', lon: '21.1207788', display_name: 'Marki, powiat wołomiński, województwo mazowieckie, Polska' }]),
    { lat: 52.3363752, lon: 21.1207788, label: 'Marki, powiat wołomiński, województwo mazowieckie' },
  );
  assert.equal(core.parseNominatim([]), null);
  assert.deepEqual(
    core.parseGugik({ results: { 1: { city: 'Krosno', street: 'Lwowska', number: '28', x: '21.7704784804004', y: '49.684033646813' } } }),
    { lat: 49.684033646813, lon: 21.7704784804004, label: 'Krosno, Lwowska 28' },
  );
  assert.equal(core.parseGugik({ results: {} }), null);
  const recs = [
    { miejscowosc: 'Krosno', lat: 49.6, lon: 21.7 },
    { miejscowosc: 'Krosno', lat: 49.8, lon: 21.9 },
    { miejscowosc: 'Marki', lat: 52.3, lon: 21.1 },
  ];
  const m = core.matchCity(recs, '  krosno ');
  assert.ok(Math.abs(m.lat - 49.7) < 1e-9 && Math.abs(m.lon - 21.8) < 1e-9 && m.label === 'Krosno');
  assert.equal(core.matchCity(recs, 'Gdańsk'), null);
});
