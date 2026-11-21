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

test('trasa w Mapach Google – zakładka „Najlepsze środki transportu”', () => {
  const url = new URL(core.routeUrl({ lat: 49.689, lon: 21.77 }, { lat: 49.6912, lon: 21.7655 }));
  assert.equal(url.origin + url.pathname, 'https://www.google.com/maps/dir/');
  assert.equal(url.searchParams.get('api'), '1');
  assert.equal(url.searchParams.get('origin'), '49.689,21.77');
  assert.equal(url.searchParams.get('destination'), '49.6912,21.7655');
  assert.equal(url.searchParams.has('travelmode'), false); // bez trybu = najlepsze środki transportu
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

test('dane strony: format zwarty, zweryfikowane i niezweryfikowane, bez fikcyjnych przykładów', () => {
  const file = path.join(__dirname, '..', 'data', 'aed-data.js');
  const ctx = { window: {} };
  vm.runInNewContext(fs.readFileSync(file, 'utf-8'), ctx);
  const data = ctx.window.AED_DATA;
  // Plik ma być lekki – ładuje się na telefonie (~18 tys. AED).
  assert.ok(fs.statSync(file).size < 3e6, 'aed-data.js > 3 MB');
  const aed = core.unpack(data);
  assert.ok(aed.length > 10000, String(aed.length));
  const verified = aed.filter(core.isVerified);
  // Pole zrodlo może łączyć kilka źródeł („danegovpl-krosno;dystrybutor”, #37).
  const parts = (r) => r.zrodlo.split(';');
  const official = (r) => parts(r).some((z) => z.startsWith('danegovpl-') || z === 'dystrybutor' || z.startsWith('dystrybutor-'));
  // Zweryfikowane = zbiory instytucji z dane.gov.pl albo potwierdzenie dystrybutora (stan main
  // 21.11 bez wczytanej listy dystrybutora: 49). Liczby nie wpisujemy na sztywno.
  assert.ok(verified.length > 0 && verified.length < aed.length / 2, String(verified.length));
  for (const r of aed) {
    assert.ok(r.lat > 49 && r.lat < 55 && r.lon > 14 && r.lon < 24.2, r.id_aed);
    assert.ok(r.zrodlo && r.licencja, r.id_aed);
    assert.ok(['zweryfikowany', 'niezweryfikowany'].includes(r.status_weryfikacji), r.id_aed);
    assert.ok(r.opis_weryfikacji, r.id_aed);
  }
  for (const r of verified) assert.ok(official(r), r.zrodlo);
  // Zdjęcia tylko ze źródeł o znanych prawach: OpenAEDMap (CC0) albo zbiór instytucji.
  const withPhoto = aed.filter((r) => r.zdjecie_url);
  // Wspólne zdjęcie wielu miejsc odrzuca ingest/ (#49); tu tylko licencja: bez pośrednika proxy.
  for (const r of withPhoto) {
    assert.ok(!r.zdjecie_url.includes('/photos/proxy/'), 'obcy obrazek przez pośrednika: ' + r.zdjecie_url);
  }
  assert.ok(withPhoto.length > 100, String(withPhoto.length));
  for (const r of withPhoto) {
    assert.ok(
      /^https:\/\/(back\.)?openaedmap\.org\/api\/v1\/photos\/view\//i.test(r.zdjecie_url) ||
        (parts(r).some((z) => z.startsWith('danegovpl-')) && /\.(jpe?g|png|webp)$/i.test(new URL(r.zdjecie_url).pathname)),
      r.zdjecie_url
    );
  }
  // Niezweryfikowane = dane społeczne z OSM albo rekord instytucji z ostrzeżeniem w opisie
  // (punkt poza jej terenem, zgłoszony przez dystrybutora brak urządzenia – #35, #37).
  for (const r of aed) {
    if (core.isVerified(r) || r.zrodlo === 'osm-openaedmap') continue;
    assert.ok(official(r), r.zrodlo);
    assert.match(r.opis_weryfikacji, /poza obszarem|brak urządzenia/, r.id_aed);
  }
  assert.equal(data.przyklady, undefined); // fikcyjne przykłady tylko w schema/, nie na stronie
  const ids = new Set(aed.map((r) => r.id_aed));
  assert.equal(ids.size, aed.length);
  // Stały kod do adresu podstrony: 10 znaków szesnastkowych, każdy da się odczytać z adresu.
  for (const r of aed.slice(0, 500)) {
    assert.match(r.id_aed, /^[0-9a-f]{10}$/);
    assert.equal(core.codeFromSlug(core.aedSlug(r)), r.id_aed);
  }
  // Każde źródło użyte w rekordach ma wpis do atrybucji w stopce.
  const sources = new Set(data.zrodla.map((s) => s.id));
  for (const r of aed) for (const z of parts(r)) assert.ok(sources.has(z), z);
});

test('unpack: format zwarty → rekordy, puste pola na końcu obcięte', () => {
  const packed = {
    pola: ['status_weryfikacji', 'zrodlo', 'nazwa_obiektu'],
    slownik: ['', 'zweryfikowany', 'danegovpl-x', 'Szkoła', 'niezweryfikowany', 'osm-openaedmap'],
    aed: [
      [5012345, 2054321, 1, 2, 3],
      [5000001, 1999999, 4, 5],
    ],
  };
  const recs = core.unpack(packed);
  assert.equal(recs.length, 2);
  assert.deepEqual(recs[0], {
    id_aed: 'aed-0', lat: 50.12345, lon: 20.54321,
    status_weryfikacji: 'zweryfikowany', zrodlo: 'danegovpl-x', nazwa_obiektu: 'Szkoła',
  });
  assert.equal(recs[1].nazwa_obiektu, '');
  assert.equal(core.isVerified(recs[0]), true);
  assert.equal(core.isVerified(recs[1]), false);
  // Stary format (lista obiektów) przechodzi bez zmian.
  const old = [{ id_aed: 'a', lat: 50, lon: 20 }];
  assert.equal(core.unpack({ aed: old }), old);
  assert.deepEqual(core.unpack(undefined), []);
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

test('matchParts: pogrubienie wpisanych słów bez względu na wielkość liter', () => {
  assert.deepEqual(core.matchParts('Wólka Orłowska 133', 'orłow'), [
    { text: 'Wólka ', match: false },
    { text: 'Orłow', match: true },
    { text: 'ska 133', match: false },
  ]);
  assert.deepEqual(core.matchParts('Krosno, Lwowska 28', 'krosno lwow'), [
    { text: 'Krosno', match: true },
    { text: ', ', match: false },
    { text: 'Lwow', match: true },
    { text: 'ska 28', match: false },
  ]);
  assert.deepEqual(core.matchParts('Abc', ''), [{ text: 'Abc', match: false }]);
  assert.deepEqual(core.matchParts('', 'x'), []);
});

test('parseOsrmTable: odległości po drogach i odrzucanie wyników mylących', () => {
  const w = (d) => ({ distance: d });
  const ok = { code: 'Ok', distances: [[0, 566.6, null, 1932.9]], sources: [w(3)], destinations: [w(3), w(1), w(2), w(5)] };
  assert.deepEqual(core.parseOsrmTable(ok, 3, [0.4, 0.5, 1.5]), [566.6, null, 1932.9]);
  // Cel daleko od drogi (np. deptak dla profilu samochodowego) → null.
  const farDest = { code: 'Ok', distances: [[0, 900]], sources: [w(3)], destinations: [w(3), w(120)] };
  assert.deepEqual(core.parseOsrmTable(farDest, 1, [0.5]), [null]);
  // Start daleko od drogi → wszystkie null.
  const farSrc = { code: 'Ok', distances: [[0, 900, 1000]], sources: [w(200)], destinations: [w(200), w(1), w(1)] };
  assert.deepEqual(core.parseOsrmTable(farSrc, 2, [0.5, 0.6]), [null, null]);
  // Trasa krótsza niż linia prosta (start i cel dociągnięte do tego samego miejsca) → null.
  const same = { code: 'Ok', distances: [[0, 0, 10]], sources: [w(60)], destinations: [w(60), w(70), w(40)] };
  assert.deepEqual(core.parseOsrmTable(same, 2, [0.04, 0.13]), [null, null]);
  assert.equal(core.parseOsrmTable({ code: 'Ok', distances: [[0, 1]] }, 3), null); // zła liczba celów
  assert.equal(core.parseOsrmTable({ code: 'TooBig' }, 1), null);
  assert.equal(core.parseOsrmTable(null, 1), null);
});

test('parseValhallaMatrix: metry, odrzucanie dalekiego dociągnięcia i tras krótszych niż linia prosta', () => {
  const from = { lat: 52.2297, lon: 20.985 };
  const targets = [{ lat: 52.231, lon: 20.99 }, { lat: 52.226, lon: 20.98 }, { lat: 52.233, lon: 20.979 }];
  const cell = (d, end, begin) => ({
    distance: d,
    begin_lat: (begin || from).lat, begin_lon: (begin || from).lon,
    end_lat: end.lat, end_lon: end.lon,
  });
  const json = { sources_to_targets: [[
    cell(0.6, targets[0]),
    cell(0.9, { lat: 52.228, lon: 20.98 }), // cel dociągnięty ~220 m dalej
    cell(0.1, targets[2]), // krócej niż linia prosta (~530 m)
  ]] };
  const straight = targets.map((t) => core.distanceKm(from, t));
  assert.deepEqual(core.parseValhallaMatrix(json, from, targets, straight), [600, null, null]);
  assert.equal(core.parseValhallaMatrix({ sources_to_targets: [[]] }, from, targets), null);
  assert.equal(core.parseValhallaMatrix(null, from, targets), null);
});

test('matchParts i fold: bez polskich znaków', () => {
  assert.equal(core.fold('Wólka ORŁOWSKA'), 'wolka orlowska');
  assert.deepEqual(core.matchParts('Wólka Orłowska', 'orlow'), [
    { text: 'Wólka ', match: false },
    { text: 'Orłow', match: true },
    { text: 'ska', match: false },
  ]);
});

test('searchAed: podpowiedzi tylko z AED, każde słowo musi pasować, potem najbliższe', () => {
  const recs = [
    { id_aed: 'a', lat: 50.06, lon: 19.94, nazwa_obiektu: 'Szkoła Podstawowa nr 1', gmina: 'Kraków', opis_lokalizacji: 'przy portierni' },
    { id_aed: 'b', lat: 50.07, lon: 19.95, nazwa_obiektu: '', gmina: 'Kraków', opis_lokalizacji: 'hol główny, szkoła' },
    { id_aed: 'c', lat: 49.69, lon: 21.77, nazwa_obiektu: 'Szkoła Muzyczna', gmina: 'Krosno', ulica: 'Lwowska' },
    { id_aed: 'd', lat: 50.0, lon: 20.0, nazwa_obiektu: 'Urząd Gminy', gmina: 'Orłów', opis_lokalizacji: '' },
  ];
  // „szkoła kraków”: oba słowa muszą pasować – c (Krosno) odpada; nazwa ważniejsza niż opis.
  assert.deepEqual(core.searchAed(recs, 'szkoła kraków').map((h) => h.rec.id_aed), ['a', 'b']);
  // Bez polskich znaków i od początku słowa.
  assert.deepEqual(core.searchAed(recs, 'orlow').map((h) => h.rec.id_aed), ['d']);
  // Ten sam wynik tekstowy – najbliżej punktu pierwszy.
  const near = { lat: 49.7, lon: 21.76 };
  assert.deepEqual(core.searchAed(recs, 'szkoła', near).map((h) => h.rec.id_aed)[0], 'c');
  assert.deepEqual(core.searchAed(recs, 'x'), []); // za krótkie słowo
  assert.equal(core.searchAed(recs, 'szkoła', null, 1).length, 1);
});

test('adres podstrony AED: czytelny, z kodem, bez polskich znaków', () => {
  const rec = {
    id_aed: '3f9a2c1b7e', miejscowosc: 'Krosno', nazwa_obiektu: 'Państwowa Akademia Nauk Stosowanych',
    wojewodztwo: 'podkarpackie', gmina: 'Krosno',
  };
  assert.equal(core.aedSlug(rec), 'aed-krosno-panstwowa-akademia-nauk-stosowanych-3f9a2c1b7e-podkarpackie');
  // Bez nazwy – opis miejsca (najwyżej 6 słów); bez miejscowości – gmina.
  assert.equal(
    core.aedSlug({ id_aed: 'abcdef0123', gmina: 'Wólka Orłowska', opis_lokalizacji: 'Na ścianie w lewym korytarzu od wejścia, obok portierni', wojewodztwo: 'lubelskie' }),
    'aed-wolka-orlowska-na-scianie-w-lewym-korytarzu-od-abcdef0123-lubelskie'
  );
  assert.equal(core.codeFromSlug('aed-krosno-3f9a2c1b7e-podkarpackie'), '3f9a2c1b7e');
  assert.equal(core.codeFromSlug('aed-krosno-podkarpackie'), null);
  assert.equal(core.codeFromSlug(''), null);
});

test('godziny i dostęp po polsku', () => {
  assert.equal(core.hoursText('24/7'), 'Całą dobę, 7 dni w tygodniu (24/7)');
  assert.equal(core.hoursText('nieznane'), 'Brak danych o godzinach dostępności');
  assert.equal(core.hoursText('Mo-Fr 07:00-21:30; Sa off'), 'pon.–pt. 07:00–21:30; sob. nieczynne');
  assert.equal(core.accessText('ograniczony').startsWith('Ograniczony'), true);
  assert.equal(core.accessText(''), 'Brak danych o dostępie');
});

test('roundStart: do serwerów tras tylko przybliżone położenie (3 miejsca po przecinku)', () => {
  assert.deepEqual(core.roundStart({ lat: 49.693049, lon: 21.765123 }), { lat: 49.693, lon: 21.765 });
  assert.deepEqual(core.roundStart({ lat: 52.22975, lon: 21.01185 }), { lat: 52.23, lon: 21.012 });
});
