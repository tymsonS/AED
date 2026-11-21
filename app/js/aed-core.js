/*
 * Logika „Znajdź AED” bez zależności od przeglądarki – testowana w Node (app/tests/).
 * - odległość (wzór haversine),
 * - godziny dostępności w składni OSM opening_hours (bezpieczny podzbiór),
 * - ocena „dostępny teraz” i wybór najbliższego AED.
 *
 * Zasada bezpieczeństwa: gdy zapisu godzin nie rozumiemy w całości, zwracamy „nieznane”,
 * nigdy „dostępny”. Lepiej odesłać do 112 niż do zamkniętych drzwi.
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.AedCore = factory();
  }
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  var DAYS = ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su'];
  var DAY_NAMES_PL = ['poniedziałek', 'wtorek', 'środa', 'czwartek', 'piątek', 'sobota', 'niedziela'];

  // --- Odległość -------------------------------------------------------------

  function distanceKm(a, b) {
    var R = 6371.0088;
    var toRad = Math.PI / 180;
    var dLat = (b.lat - a.lat) * toRad;
    var dLon = (b.lon - a.lon) * toRad;
    var h =
      Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos(a.lat * toRad) * Math.cos(b.lat * toRad) * Math.sin(dLon / 2) * Math.sin(dLon / 2);
    return 2 * R * Math.asin(Math.min(1, Math.sqrt(h)));
  }

  function formatDistance(km) {
    if (km < 1) {
      return Math.max(10, Math.round((km * 1000) / 10) * 10) + ' m';
    }
    if (km < 10) {
      return km.toFixed(1).replace('.', ',') + ' km';
    }
    return Math.round(km) + ' km';
  }

  // --- Godziny (opening_hours) ----------------------------------------------

  function parseTime(t) {
    var m = /^(\d{1,2}):(\d{2})$/.exec(t);
    if (!m) return null;
    var h = Number(m[1]);
    var min = Number(m[2]);
    if (h > 24 || min > 59 || (h === 24 && min !== 0)) return null;
    return h * 60 + min;
  }

  function parseDays(spec) {
    // "Mo-Fr", "Sa,Su", "Mo-We,Fr", "Fr-Mo" (zawijanie przez niedzielę)
    var days = [];
    var parts = spec.split(',');
    for (var i = 0; i < parts.length; i++) {
      var p = parts[i];
      var range = p.split('-');
      if (range.length === 1) {
        var d = DAYS.indexOf(range[0]);
        if (d < 0) return null;
        days.push(d);
      } else if (range.length === 2) {
        var a = DAYS.indexOf(range[0]);
        var b = DAYS.indexOf(range[1]);
        if (a < 0 || b < 0) return null;
        for (var k = a; ; k = (k + 1) % 7) {
          days.push(k);
          if (k === b) break;
        }
      } else {
        return null;
      }
    }
    return days;
  }

  /**
   * Zwraca { always: true } dla „24/7”, { rules: [...] } dla obsługiwanych zapisów
   * albo null, gdy godzin nie znamy lub zapisu nie rozumiemy.
   */
  function parseOpeningHours(value) {
    if (typeof value !== 'string') return null;
    var text = value.trim();
    if (!text || text.toLowerCase() === 'nieznane') return null;
    if (text === '24/7') return { always: true };

    var rules = [];
    var chunks = text.split(';');
    for (var i = 0; i < chunks.length; i++) {
      var chunk = chunks[i].trim();
      if (!chunk) continue;
      var m = /^(?:([A-Za-z,\-]+)\s+)?(.+)$/.exec(chunk);
      if (!m) return null;
      var daySpec = m[1];
      var timeSpec = m[2].trim();
      // Sam dzień bez godzin, np. "Mo-Fr" – niejednoznaczne, nie zgadujemy.
      if (!daySpec && /^[A-Za-z,\-]+$/.test(timeSpec)) {
        if (timeSpec === 'off' || timeSpec === 'closed') {
          rules.push({ days: [0, 1, 2, 3, 4, 5, 6], off: true });
          continue;
        }
        return null;
      }
      var days = daySpec ? parseDays(daySpec) : [0, 1, 2, 3, 4, 5, 6];
      if (!days) return null; // np. PH, SH, miesiące – nie obsługujemy
      if (timeSpec === 'off' || timeSpec === 'closed') {
        rules.push({ days: days, off: true });
        continue;
      }
      var ranges = [];
      var spans = timeSpec.split(',');
      for (var j = 0; j < spans.length; j++) {
        var se = spans[j].trim().split('-');
        if (se.length !== 2) return null;
        var start = parseTime(se[0]);
        var end = parseTime(se[1]);
        if (start === null || end === null || start === end) return null;
        ranges.push([start, end]);
      }
      rules.push({ days: days, ranges: ranges });
    }
    if (!rules.length) return null;
    return { rules: rules };
  }

  // Reguły późniejsze nadpisują wcześniejsze dla dni, które wymieniają (semantyka OSM).
  function rangesForDay(parsed, day) {
    var result = [];
    for (var i = 0; i < parsed.rules.length; i++) {
      var r = parsed.rules[i];
      if (r.days.indexOf(day) >= 0) {
        result = r.off ? [] : r.ranges;
      }
    }
    return result;
  }

  function dayIndex(date) {
    return (date.getDay() + 6) % 7; // pn = 0 … nd = 6
  }

  /**
   * Czy otwarte w danej chwili (czas lokalny przeglądarki).
   * Zwraca { known: false } albo { known: true, open: bool, until?: 'HH:MM' }.
   */
  function openAt(value, date) {
    var parsed = parseOpeningHours(value);
    if (!parsed) return { known: false };
    if (parsed.always) return { known: true, open: true, always: true };

    var day = dayIndex(date);
    var minutes = date.getHours() * 60 + date.getMinutes();
    var today = rangesForDay(parsed, day);
    for (var i = 0; i < today.length; i++) {
      var s = today[i][0];
      var e = today[i][1];
      if (e > s && minutes >= s && minutes < e) return { known: true, open: true, until: fmt(e) };
      if (e < s && minutes >= s) return { known: true, open: true, until: fmt(e) }; // przez północ
    }
    var yesterday = rangesForDay(parsed, (day + 6) % 7);
    for (var k = 0; k < yesterday.length; k++) {
      var ys = yesterday[k][0];
      var ye = yesterday[k][1];
      if (ye < ys && minutes < ye) return { known: true, open: true, until: fmt(ye) };
    }
    return { known: true, open: false };
  }

  function fmt(minutes) {
    var h = Math.floor(minutes / 60) % 24;
    var m = minutes % 60;
    return (h < 10 ? '0' : '') + h + ':' + (m < 10 ? '0' : '') + m;
  }

  // --- Dostępność AED ---------------------------------------------------------

  /**
   * Ocena dostępności rekordu teraz: 'dostepny' | 'niedostepny' | 'nieznany'
   * + krótki opis dla człowieka.
   */
  function availability(rec, date) {
    if (rec.status === 'nieaktywny' || rec.status === 'w_serwisie') {
      return { state: 'niedostepny', label: rec.status === 'w_serwisie' ? 'W serwisie' : 'Nieaktywny' };
    }
    if (rec.dostep === 'prywatny') {
      return { state: 'niedostepny', label: 'Dostęp prywatny' };
    }
    var hours = openAt(rec.godziny_dostepnosci, date);
    if (!hours.known) {
      return { state: 'nieznany', label: 'Godziny nieznane' };
    }
    if (!hours.open) {
      return { state: 'niedostepny', label: 'Teraz zamknięte' };
    }
    if (hours.always) {
      return { state: 'dostepny', label: 'Dostępny teraz · całą dobę' };
    }
    return { state: 'dostepny', label: 'Dostępny teraz · do ' + hours.until };
  }

  /**
   * Sortuje AED wg odległości od punktu i wskazuje AED do wyróżnienia:
   * najbliższy „dostępny teraz”, a gdy takiego nie ma – najbliższy w ogóle
   * (z flagą fallback, żeby interfejs mógł to uczciwie opisać).
   */
  function rank(records, point, date) {
    var list = records.map(function (rec) {
      return {
        rec: rec,
        km: distanceKm(point, rec),
        availability: availability(rec, date),
      };
    });
    list.sort(function (a, b) {
      return a.km - b.km;
    });
    var highlight = null;
    var fallback = false;
    for (var i = 0; i < list.length; i++) {
      if (list[i].availability.state === 'dostepny') {
        highlight = list[i];
        break;
      }
    }
    if (!highlight && list.length) {
      highlight = list[0];
      fallback = true;
    }
    return { list: list, highlight: highlight, fallback: fallback };
  }

  // Tylko prezentacja: obcina separatory na końcu pól (np. „Kazimierza Wielkiego 4,” w danych źródłowych).
  function clean(value) {
    return String(value || '').replace(/[\s,;]+$/, '').trim();
  }

  function address(rec) {
    var street = [clean(rec.ulica), clean(rec.numer_budynku)].filter(Boolean).join(' ');
    var city = [clean(rec.kod_pocztowy), clean(rec.miejscowosc)].filter(Boolean).join(' ');
    return [street, city].filter(Boolean).join(', ');
  }

  /**
   * Link do trasy pieszej w Mapach Google (oficjalny format „Maps URLs”, bez klucza API).
   * Na telefonie otwiera aplikację Map Google, jeśli jest zainstalowana.
   */
  function routeUrl(from, to) {
    return (
      'https://www.google.com/maps/dir/?api=1' +
      '&origin=' + encodeURIComponent(from.lat + ',' + from.lon) +
      '&destination=' + encodeURIComponent(to.lat + ',' + to.lon) +
      '&travelmode=walking'
    );
  }

  /**
   * Wyniki jak w wyszukiwarkach punktów: tylko w promieniu radiusKm (lista z rank()),
   * opcjonalnie tylko „dostępne teraz”. nearestOutside = najbliższy pasujący spoza promienia.
   */
  function inRadius(rankedList, radiusKm, onlyAvailable) {
    var matching = rankedList.filter(function (item) {
      return !onlyAvailable || item.availability.state === 'dostepny';
    });
    var inside = matching.filter(function (item) {
      return item.km <= radiusKm;
    });
    var outside = matching.filter(function (item) {
      return item.km > radiusKm;
    });
    return { items: inside, nearestOutside: outside.length ? outside[0] : null };
  }

  // --- Dane w formacie zwartym (app/scripts/build_data.py) ---------------

  /**
   * Rozpakowuje { pola, slownik, aed: [[szer*1e5, dl*1e5, indeksy...]] } do zwykłych rekordów
   * z polami lat, lon, id_aed (lokalne, tylko dla interfejsu) i przyklad = false.
   * Stary format (aed jako lista obiektów) zwraca bez zmian.
   */
  function unpack(data) {
    if (!data) return [];
    var rows = data.aed || [];
    if (!data.pola || !data.slownik) return rows; // stary format
    var fields = data.pola;
    var table = data.slownik;
    return rows.map(function (row, i) {
      var rec = { id_aed: 'aed-' + i, lat: row[0] / 1e5, lon: row[1] / 1e5, przyklad: false };
      for (var f = 0; f < fields.length; f++) {
        var idx = row[f + 2];
        rec[fields[f]] = idx == null ? '' : table[idx] || '';
      }
      return rec;
    });
  }

  /** Status weryfikacji z eksportu ingest/: zweryfikowany (dane instytucji) albo nie. */
  function isVerified(rec) {
    return rec.status_weryfikacji === 'zweryfikowany';
  }

  // --- Geokodowanie (parsowanie odpowiedzi; zapytania wysyła app.js) --------

  /** Nominatim (OSM), format=jsonv2 → { lat, lon, label } albo null. */
  function parseNominatim(json) {
    if (!Array.isArray(json) || !json.length) return null;
    var r = json[0];
    var lat = Number(r.lat);
    var lon = Number(r.lon);
    if (!isFinite(lat) || !isFinite(lon)) return null;
    return { lat: lat, lon: lon, label: String(r.display_name || '').split(',').slice(0, 3).join(',') };
  }

  /** GUGiK UUG GetAddress z srid=4326 (x = długość, y = szerokość) → { lat, lon, label } albo null. */
  function parseGugik(json) {
    var results = json && json.results;
    if (!results) return null;
    var keys = Object.keys(results);
    if (!keys.length) return null;
    var r = results[keys[0]];
    var lat = Number(r.y);
    var lon = Number(r.x);
    if (!isFinite(lat) || !isFinite(lon)) return null;
    var label = [r.city, [r.street, r.number].filter(Boolean).join(' ')].filter(Boolean).join(', ');
    return { lat: lat, lon: lon, label: label };
  }

  /** Dopasowanie do miejscowości z naszych danych (bez sieci): środek AED w tej miejscowości. */
  function matchCity(records, query) {
    var q = String(query || '').trim().toLocaleLowerCase('pl');
    if (!q) return null;
    var hits = records.filter(function (r) {
      return String(r.miejscowosc || '').toLocaleLowerCase('pl') === q;
    });
    if (!hits.length) return null;
    var lat = 0;
    var lon = 0;
    hits.forEach(function (r) {
      lat += r.lat;
      lon += r.lon;
    });
    return { lat: lat / hits.length, lon: lon / hits.length, label: hits[0].miejscowosc };
  }

  return {
    inRadius: inRadius,
    unpack: unpack,
    isVerified: isVerified,
    parseNominatim: parseNominatim,
    parseGugik: parseGugik,
    matchCity: matchCity,
    routeUrl: routeUrl,
    distanceKm: distanceKm,
    formatDistance: formatDistance,
    parseOpeningHours: parseOpeningHours,
    openAt: openAt,
    availability: availability,
    rank: rank,
    address: address,
    DAY_NAMES_PL: DAY_NAMES_PL,
  };
});
