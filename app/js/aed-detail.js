/*
 * Znajdź AED – podstrona jednego AED (aed.html?aed=<adres>), jak strona paczkomatu po „Szczegóły”.
 * Adres: aed-<miejscowość>-<nazwa>-<kod>-<województwo> (AedCore.aedSlug); AED rozpoznajemy po kodzie.
 * Kolejność treści – od najważniejszej: co to i czy dostępny teraz, jak dojść, kiedy i dla kogo,
 * gdzie dokładnie, kto odpowiada, skąd dane. Teksty z danych wstawiamy wyłącznie przez esc().
 */
(function () {
  'use strict';

  var Core = window.AedCore;
  var RAW = window.AED_DATA || {};
  var OSRM_FOOT = 'https://routing.openstreetmap.de/routed-foot/table/v1/driving/';
  var VALHALLA = 'https://valhalla1.openstreetmap.de/sources_to_targets?json=';
  var box = document.getElementById('aed');

  function esc(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function safeUrl(url) {
    return /^https?:\/\//i.test(url || '') ? url : '';
  }

  function storedPoint() {
    try {
      var p = JSON.parse(sessionStorage.getItem('aed-point') || 'null');
      return p && isFinite(p.lat) && isFinite(p.lon) ? p : null;
    } catch (e) {
      return null;
    }
  }

  function rememberPoint(point) {
    try {
      sessionStorage.setItem('aed-point', JSON.stringify(point));
    } catch (e) {}
  }

  var slug = new URLSearchParams(location.search).get('aed');
  var code = Core.codeFromSlug(slug);
  var rec = null;
  if (code) {
    Core.unpack(RAW).some(function (r) {
      if (r.id_aed === code) rec = r;
      return !!rec;
    });
  }

  if (!rec) {
    box.innerHTML =
      '<h1 class="page-title">Nie znaleźliśmy tego AED</h1>' +
      '<p>Link może być nieaktualny albo AED zniknął z danych (np. dystrybutor zgłosił, że urządzenia już nie ma).</p>' +
      '<p><a class="btn btn-primary" href="index.html">Wróć do wyszukiwarki</a></p>';
    document.title = 'Nie znaleziono AED – Znajdź AED';
    return;
  }

  // Kanoniczny adres (np. gdy nazwa w danych się zmieniła, a ktoś otworzył stary link).
  var canonical = Core.aedSlug(rec);
  if (canonical !== slug && history.replaceState) {
    history.replaceState(null, '', 'aed.html?aed=' + encodeURIComponent(canonical));
  }

  var name = rec.nazwa_obiektu || 'AED';
  var place = rec.miejscowosc || rec.gmina || '';
  var verified = Core.isVerified(rec);
  var avail = Core.availability(rec, new Date());
  var availLabel = avail.label + (rec.dostep === 'ograniczony' ? ' · dostęp ograniczony' : '');
  var source = (RAW.zrodla || []).filter(function (s) {
    return String(rec.zrodlo).split(';').indexOf(s.id) !== -1;
  });

  document.title = name + (place ? ', ' + place : '') + ' – Znajdź AED';
  var crumb = document.getElementById('crumb-name');
  if (crumb) crumb.textContent = name;

  function row(label, value, html) {
    if (!value && !html) return '';
    return '<dt>' + esc(label) + '</dt><dd>' + (html || esc(value)) + '</dd>';
  }

  function section(id, title, body) {
    if (!body) return '';
    return '<section class="aed-section" aria-labelledby="' + id + '"><h2 id="' + id + '">' + esc(title) + '</h2>' + body + '</section>';
  }

  function routeUrl() {
    var p = storedPoint();
    // Bez zapamiętanego punktu Mapy Google wezmą położenie telefonu jako start.
    if (p) return Core.routeUrl(p, rec);
    return 'https://www.google.com/maps/dir/?api=1&destination=' + encodeURIComponent(rec.lat + ',' + rec.lon);
  }

  var verifyTag =
    '<span class="verify verify--' + (verified ? 'yes' : 'no') + '">' +
    (verified ? '<svg viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M6.4 11.6 2.8 8l1.1-1.1 2.5 2.5 5.7-5.7 1.1 1.1z" fill="currentColor"/></svg>' : '') +
    (verified ? 'Zweryfikowany' : 'Niezweryfikowany') + '</span>';

  var address = Core.address(rec);
  var where = address || rec.opis_lokalizacji || '';

  // 1. Co to, czy dostępny teraz, główne akcje
  var top =
    '<div class="aed-detail__top">' +
    '<div class="aed-detail__main">' +
    '<p class="aed-detail__status"><span class="badge badge-' + avail.state + '">' + esc(availLabel) + '</span>' + verifyTag + '</p>' +
    '<h1 class="page-title">' + esc(name) + '</h1>' +
    (where ? '<p class="aed-detail__where">' + esc(where) + '</p>' : '') +
    (address && rec.opis_lokalizacji ? '<p class="aed-detail__desc">' + esc(rec.opis_lokalizacji) + '</p>' : '') +
    '<p class="aed-detail__place">' + esc([rec.gmina ? 'gm. ' + rec.gmina : '', rec.wojewodztwo ? 'woj. ' + rec.wojewodztwo : ''].filter(Boolean).join(', ')) + '</p>' +
    '<div class="aed-detail__distance" id="distance"></div>' +
    '<p class="aed-detail__actions">' +
    '<a class="btn btn-primary" href="' + esc(routeUrl()) + '" target="_blank" rel="noopener">Wyznacz trasę<span class="visually-hidden"> (Mapy Google, nowa karta)</span></a>' +
    '<a class="btn btn-outline" href="index.html?aed=' + esc(encodeURIComponent(canonical)) + '">Pokaż na mapie</a>' +
    '</p>' +
    '</div>' +
    '<div id="aed-map" class="aed-detail__map" role="img" aria-label="Mapa z położeniem AED"></div>' +
    '</div>';

  // 2. Kiedy i dla kogo
  var when = '<dl class="aed-facts">' +
    row('Teraz', availLabel) +
    row('Godziny dostępności', Core.hoursText(rec.godziny_dostepnosci)) +
    row('Dostęp', Core.accessText(rec.dostep)) +
    '</dl>';

  // 3. Gdzie dokładnie
  var osm = 'https://www.openstreetmap.org/?mlat=' + rec.lat.toFixed(6) + '&mlon=' + rec.lon.toFixed(6) + '#map=19/' + rec.lat.toFixed(6) + '/' + rec.lon.toFixed(6);
  var whereSec = '<dl class="aed-facts">' +
    row('Opis miejsca', rec.opis_lokalizacji) +
    row('Adres', address) +
    row('Gmina', rec.gmina) +
    row('Województwo', rec.wojewodztwo) +
    row('Współrzędne', null, esc(rec.lat.toFixed(6) + ', ' + rec.lon.toFixed(6)) +
      ' · <a href="' + esc(osm) + '" target="_blank" rel="noopener">OpenStreetMap<span class="visually-hidden"> (nowa karta)</span></a>') +
    '</dl>';

  // 4. Kto odpowiada
  var phone = rec.telefon_kontaktowy;
  var who = '<dl class="aed-facts">' +
    row('Dysponent', rec.dysponent_nazwa || 'Brak danych – nie wiadomo, kto odpowiada za to urządzenie') +
    row('Telefon', null, phone ? '<a href="tel:' + esc(phone.replace(/\s+/g, '')) + '">' + esc(phone) + '</a>' : '') +
    '</dl>';

  // 5. Skąd dane
  var src = source.map(function (s) {
    var url = safeUrl(s.url);
    var label = esc(s.nazwa || s.id) + (s.dysponent ? ' – ' + esc(s.dysponent) : '');
    return (url ? '<a href="' + esc(url) + '">' + label + '</a>' : label) +
      (s.licencja === 'ODbL-1.0' ? ' (© autorzy <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>, ODbL 1.0)' : '');
  }).join('<br />');
  var data = '<dl class="aed-facts">' +
    row('Status', null, verifyTag) +
    row('Weryfikacja', rec.opis_weryfikacji) +
    row('Źródło', null, src || esc(rec.zrodlo)) +
    row('Licencja', rec.licencja) +
    row('Kod AED', rec.id_aed) +
    row('Dane zbudowano', RAW.wygenerowano ? new Date(RAW.wygenerowano).toLocaleString('pl-PL') : '') +
    '</dl>';

  box.innerHTML =
    top +
    section('h-kiedy', 'Kiedy i dla kogo', when) +
    section('h-gdzie', 'Gdzie dokładnie', whereSec) +
    section('h-kto', 'Kto odpowiada', who) +
    section('h-dane', 'Weryfikacja i źródło danych', data);

  // --- Mini mapa -------------------------------------------------------------

  if (window.L) {
    var map = L.map('aed-map', { scrollWheelZoom: false, zoomControl: true }).setView([rec.lat, rec.lon], 17);
    map.attributionControl.setPrefix('<a href="https://leafletjs.com">Leaflet</a>');
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; autorzy <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(map);
    var color = { dostepny: '#1e7b34', nieznany: '#5e5e5e', niedostepny: '#a91e2c' }[avail.state];
    L.marker([rec.lat, rec.lon], {
      keyboard: false,
      icon: L.divIcon({
        className: 'pin is-top',
        html:
          '<svg viewBox="0 0 30 40" aria-hidden="true" focusable="false">' +
          '<path d="M15 39s13-14.4 13-24A13 13 0 0 0 2 15c0 9.6 13 24 13 24z" fill="' + color + '" stroke="#fff" stroke-width="2"/>' +
          '<path d="M15 23s-6-3.6-6-8.2A3.5 3.5 0 0 1 15 12.4a3.5 3.5 0 0 1 6 2.4c0 4.6-6 8.2-6 8.2z" fill="#fff"/>' +
          '<path d="M15.6 13.6 13.4 17h1.7l-.7 2.7 2.6-3.6h-1.8z" fill="' + color + '"/>' +
          (verified
            ? '<circle cx="24" cy="7" r="6.5" fill="#fff" stroke="' + color + '" stroke-width="1.5"/>' +
              '<path d="M21.2 7.1l2 2 3.7-3.9" fill="none" stroke="#0f2648" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>'
            : '') +
          '</svg>',
        iconSize: [44, 58],
        iconAnchor: [22, 58],
      }),
    }).addTo(map);
  }

  // --- Odległość: w linii prostej i po drogach -----------------------------

  var distBox = document.getElementById('distance');
  var ICON_WALK =
    '<svg class="route-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">' +
    '<circle cx="13.5" cy="4" r="2.2" fill="currentColor"/>' +
    '<path d="M12.4 7.6 9 9.4 7.6 13l1.7.6 1.1-2.8 1.3-.6-1.3 5.4L7 21l1.6 1 3.5-4.4 2.1 2V22H16v-4.2l-2.3-2.4.8-3.4 1.2 1.6 3.3 1v-1.8l-2.3-.8-1.7-2.9a2.2 2.2 0 0 0-2.6-1.5z" fill="currentColor"/></svg>';
  var ICON_CAR =
    '<svg class="route-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">' +
    '<path d="M6.3 5.5A2 2 0 0 1 8.2 4h7.6a2 2 0 0 1 1.9 1.5L19 10h.5A1.5 1.5 0 0 1 21 11.5V18h-2v2h-3v-2H8v2H5v-2H3v-6.5A1.5 1.5 0 0 1 4.5 10H5zM7.3 10h9.4l-1-3.6a.6.6 0 0 0-.6-.4H8.9a.6.6 0 0 0-.6.4zM7 15.5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3zm10 0a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3z" fill="currentColor"/></svg>';

  function part(icon, label, m) {
    var text = m === undefined ? '…' : m === null ? '–' : Core.formatDistance(m / 1000);
    var sr = m === undefined ? 'liczymy' : m === null ? 'brak trasy' : Core.formatDistance(m / 1000);
    return '<span class="route-part">' + icon + '<span aria-hidden="true">' + esc(text) + '</span>' +
      '<span class="visually-hidden">' + esc(label + ' ' + sr) + '</span></span>';
  }

  function fetchJson(url, timeoutMs) {
    var ctrl = window.AbortController ? new AbortController() : null;
    var timer = setTimeout(function () { if (ctrl) ctrl.abort(); }, timeoutMs || 8000);
    return fetch(url, { headers: { Accept: 'application/json' }, signal: ctrl ? ctrl.signal : undefined })
      .then(function (r) {
        clearTimeout(timer);
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      });
  }

  function showDistance(point) {
    var km = Core.distanceKm(point, rec);
    var state = { foot: undefined, car: undefined };
    function paint() {
      distBox.innerHTML =
        '<p class="aed-detail__km"><span class="distance">' + esc(Core.formatDistance(km)) +
        '<span class="distance-note"> w linii prostej' + (point.label ? ' od: ' + esc(point.label) : '') + '</span></span></p>' +
        '<p class="routes">' + part(ICON_WALK, 'pieszo', state.foot) + part(ICON_CAR, 'samochodem', state.car) + '</p>';
    }
    paint();
    var pt = function (r) { return { lat: +r.lat.toFixed(6), lon: +r.lon.toFixed(6) }; };
    var start = Core.roundStart(point); // serwer tras nie dostaje dokładnego położenia
    var kmStart = Core.distanceKm(start, rec);
    var valhalla = function (costing) {
      return fetchJson(VALHALLA + encodeURIComponent(JSON.stringify({ sources: [pt(start)], targets: [pt(rec)], costing: costing, units: 'kilometers' })))
        .then(function (json) { return Core.parseValhallaMatrix(json, start, [rec], [kmStart]); });
    };
    var carSent = Date.now();
    valhalla('auto')
      .catch(function () { return null; })
      .then(function (d) { state.car = d ? d[0] : null; paint(); });
    // Pieszo: OSRM; gdy nie odpowie w 4 s (albo odmówi) – Valhalla, nie wcześniej niż 1,1 s
    // po zapytaniu o samochód (limit serwerów FOSSGIS: 1 zapytanie na sekundę).
    fetchJson(OSRM_FOOT + start.lon.toFixed(3) + ',' + start.lat.toFixed(3) + ';' + rec.lon.toFixed(6) + ',' + rec.lat.toFixed(6) + '?sources=0&annotations=distance', 4000)
      .then(function (json) { return Core.parseOsrmTable(json, 1, [kmStart]); })
      .catch(function () {
        return new Promise(function (resolve) {
          setTimeout(resolve, Math.max(0, carSent + 1100 - Date.now()));
        }).then(function () { return valhalla('pedestrian'); }).catch(function () { return null; });
      })
      .then(function (d) { state.foot = d ? d[0] : null; paint(); });
  }

  var start = storedPoint();
  if (start) {
    showDistance(start);
  } else if (navigator.geolocation) {
    distBox.innerHTML = '<p><button type="button" class="btn btn-outline btn-sm" id="detail-locate">Pokaż odległość od mojego położenia</button></p>';
    document.getElementById('detail-locate').addEventListener('click', function () {
      distBox.innerHTML = '<p>Ustalamy położenie…</p>';
      navigator.geolocation.getCurrentPosition(
        function (pos) {
          var p = { lat: pos.coords.latitude, lon: pos.coords.longitude, label: 'Twoja lokalizacja' };
          rememberPoint(p);
          showDistance(p);
        },
        function () {
          distBox.innerHTML = '<p>Nie udało się ustalić położenia. Trasę pokażą Mapy Google po kliknięciu „Wyznacz trasę”.</p>';
        },
        { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 }
      );
    });
  }
})();
