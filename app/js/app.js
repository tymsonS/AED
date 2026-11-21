/*
 * Znajdź AED – interfejs (układ jak wyszukiwarka paczkomatów: mapa + panel z wynikami).
 * Logika (odległości, godziny, ranking, promień, parsowanie geokoderów) – aed-core.js.
 * Dane: window.AED_DATA z data/aed-data.js. Teksty z danych wstawiamy wyłącznie jako tekst (esc()).
 */
(function () {
  'use strict';

  var Core = window.AedCore;
  var RAW = window.AED_DATA || {};
  var DATA = {
    aed: Core.unpack(RAW), // format zwarty → zwykłe rekordy (aed-core.js)
    przyklady: RAW.przyklady || [],
    zrodla: RAW.zrodla || [],
    wygenerowano: RAW.wygenerowano,
  };
  var POLAND = { center: [52.1, 19.4], zoom: 6 };
  var RADIUS_KM = 5;
  var LIST_PAGE = 50; // ~18 tys. AED – lista dokłada wyniki porcjami, żeby nie zablokować telefonu
  var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  var state = {
    point: null, // { lat, lon, label }
    showExamples: false,
    onlyAvailable: false,
    selectedId: null,
    ranked: null,
    listLimit: LIST_PAGE,
  };

  var el = {
    locate: document.getElementById('locate'),
    form: document.getElementById('search-form'),
    search: document.getElementById('search'),
    tabs: document.querySelectorAll('.finder-tab'),
    showExamples: document.getElementById('show-examples'),
    status: document.getElementById('status'),
    highlight: document.getElementById('highlight'),
    list: document.getElementById('list'),
    listSummary: document.getElementById('list-summary'),
    dataSummary: document.getElementById('data-summary'),
    sources: document.getElementById('sources'),
  };

  var map = null;
  var clusterLayer = null;
  var topLayer = null;
  var meMarker = null;
  var radiusCircle = null;
  var markersById = {};

  // --- Pomocnicze ------------------------------------------------------------

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

  function records() {
    return state.showExamples ? DATA.aed.concat(DATA.przyklady) : DATA.aed.slice();
  }

  function setStatus(text, warning) {
    el.status.textContent = text || '';
    el.status.classList.toggle('is-warning', !!warning);
  }

  function stateClass(item) {
    return item.rec.przyklad ? 'przyklad' : item.availability.state;
  }

  /** Krótki opis weryfikacji do listy i dymków (tekst, nie tylko kolor/ikona). */
  function verifyLabel(rec) {
    if (rec.przyklad) return 'Przykład (fikcyjny)';
    return Core.isVerified(rec) ? 'Zweryfikowany' : 'Niezweryfikowany';
  }

  function verifyTag(rec) {
    if (rec.przyklad) return '';
    var ok = Core.isVerified(rec);
    return '<span class="verify verify--' + (ok ? 'yes' : 'no') + '">' +
      (ok ? '<svg viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M6.4 11.6 2.8 8l1.1-1.1 2.5 2.5 5.7-5.7 1.1 1.1z" fill="currentColor"/></svg>' : '') +
      esc(verifyLabel(rec)) + '</span>';
  }

  /** Adres; gdy go brak (większość danych z OSM) – opis miejsca. */
  function where(rec) {
    return Core.address(rec) || rec.opis_lokalizacji || '';
  }

  function routeLink(rec, cls, text) {
    if (!state.point || rec.przyklad) return '';
    return (
      '<a class="' + cls + '" href="' + esc(Core.routeUrl(state.point, rec)) + '" target="_blank" rel="noopener">' +
      esc(text) + '<span class="visually-hidden"> do ' + esc(rec.nazwa_obiektu) + ' (Mapy Google, nowa karta)</span></a>'
    );
  }

  // --- Mapa ------------------------------------------------------------------

  var PIN_COLORS = { dostepny: '#1e7b34', nieznany: '#5e5e5e', niedostepny: '#a91e2c', przyklad: '#8a6a00' };

  // Zweryfikowany AED ma na pinezce białą odznakę z „✓” (kształt, nie tylko kolor).
  function pinIcon(kind, top, verified) {
    var color = PIN_COLORS[kind];
    var svg =
      '<svg viewBox="0 0 30 40" aria-hidden="true" focusable="false">' +
      '<path d="M15 39s13-14.4 13-24A13 13 0 0 0 2 15c0 9.6 13 24 13 24z" fill="' + color + '" stroke="#fff" stroke-width="2"' +
      (kind === 'przyklad' ? ' stroke-dasharray="3 2"' : '') + '/>' +
      '<path d="M15 23s-6-3.6-6-8.2A3.5 3.5 0 0 1 15 12.4a3.5 3.5 0 0 1 6 2.4c0 4.6-6 8.2-6 8.2z" fill="#fff"/>' +
      '<path d="M15.6 13.6 13.4 17h1.7l-.7 2.7 2.6-3.6h-1.8z" fill="' + color + '"/>' +
      (verified
        ? '<circle cx="24" cy="7" r="6.5" fill="#fff" stroke="' + color + '" stroke-width="1.5"/>' +
          '<path d="M21.2 7.1l2 2 3.7-3.9" fill="none" stroke="#0f2648" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>'
        : '') +
      '</svg>';
    var size = top ? [44, 58] : [30, 40];
    return L.divIcon({
      className: 'pin' + (top ? ' is-top' : '') + (verified ? ' is-verified' : ''),
      html: svg,
      iconSize: size,
      iconAnchor: [size[0] / 2, size[1]],
      popupAnchor: [0, -size[1] + 6],
    });
  }

  function clusterIcon(cluster) {
    var n = cluster.getChildCount();
    return L.divIcon({
      className: 'cluster',
      html: '<span>' + n + '</span>',
      iconSize: [40, 40],
    });
  }

  function initMap() {
    if (map) return;
    map = L.map('map', { zoomControl: true, scrollWheelZoom: true }).setView(POLAND.center, POLAND.zoom);
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; autorzy <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> · AED: <a href="https://openaedmap.org">OpenAEDMap</a> (ODbL)',
    }).addTo(map);
    clusterLayer = L.markerClusterGroup
      ? L.markerClusterGroup({ showCoverageOnHover: false, maxClusterRadius: 50, iconCreateFunction: clusterIcon })
      : L.layerGroup();
    clusterLayer.addTo(map);
    topLayer = L.layerGroup().addTo(map);
    map.on('click', function (e) {
      setPoint({ lat: e.latlng.lat, lon: e.latlng.lng, label: 'punkt wskazany na mapie' }, 'map');
    });
  }

  // --- Odległość po drogach: pieszo i samochodem -------------------------
  // Serwer tras FOSSGIS (OSRM na danych OpenStreetMap, profile foot i car). Zasady: maks.
  // 1 zapytanie na sekundę, bez intensywnego użycia – dlatego jedno zapytanie „table” na tryb
  // dla widocznych wyników (do 25 AED naraz), kolejka z odstępem 1,1 s i pamięć wyników.
  // Mapy Google: ich odległości wymagają płatnego klucza API, a regulamin nie pozwala
  // pokazywać ich na mapie innej niż Google – dlatego Google tylko w linku „Wyznacz trasę”.

  var ROUTES_URL = 'https://routing.openstreetmap.de/routed-';
  var ROUTES_MAX = 25;
  var routes = { cache: {}, queue: [], busy: false, last: 0 };

  var ICON_WALK =
    '<svg class="route-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">' +
    '<circle cx="13.5" cy="4" r="2.2" fill="currentColor"/>' +
    '<path d="M12.4 7.6 9 9.4 7.6 13l1.7.6 1.1-2.8 1.3-.6-1.3 5.4L7 21l1.6 1 3.5-4.4 2.1 2V22H16v-4.2l-2.3-2.4.8-3.4 1.2 1.6 3.3 1v-1.8l-2.3-.8-1.7-2.9a2.2 2.2 0 0 0-2.6-1.5z" fill="currentColor"/></svg>';
  var ICON_CAR =
    '<svg class="route-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">' +
    '<path d="M6.3 5.5A2 2 0 0 1 8.2 4h7.6a2 2 0 0 1 1.9 1.5L19 10h.5A1.5 1.5 0 0 1 21 11.5V18h-2v2h-3v-2H8v2H5v-2H3v-6.5A1.5 1.5 0 0 1 4.5 10H5zM7.3 10h9.4l-1-3.6a.6.6 0 0 0-.6-.4H8.9a.6.6 0 0 0-.6.4zM7 15.5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3zm10 0a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3z" fill="currentColor"/></svg>';

  function pointKey(pt) {
    return pt.lat.toFixed(5) + ',' + pt.lon.toFixed(5);
  }

  function routeKey(mode, rec) {
    return state.point ? mode + '|' + pointKey(state.point) + '|' + rec.id_aed : '';
  }

  /** „🚶 600 m  🚗 500 m” albo „…” w trakcie; puste, gdy brak punktu lub usługa nie odpowiada. */
  function routesHtml(rec) {
    if (!state.point || rec.przyklad) return '';
    var walk = routes.cache[routeKey('foot', rec)];
    var car = routes.cache[routeKey('car', rec)];
    if (walk === false && car === false) return ''; // usługa niedostępna – zostaje odległość w linii prostej
    var part = function (icon, label, m) {
      var text = m === undefined ? '…' : m === null || m === false ? '–' : Core.formatDistance(m / 1000);
      var sr = m === undefined ? 'liczymy' : m === null || m === false ? 'brak trasy' : Core.formatDistance(m / 1000);
      return '<span class="route-part">' + icon + '<span aria-hidden="true">' + esc(text) + '</span>' +
        '<span class="visually-hidden">' + esc(label + ' ' + sr) + '</span></span>';
    };
    return '<span class="routes" data-routes="' + esc(rec.id_aed) + '">' +
      part(ICON_WALK, 'pieszo', walk) + part(ICON_CAR, 'samochodem', car) + '</span>';
  }

  function paintRoutes() {
    Array.prototype.forEach.call(document.querySelectorAll('[data-routes]'), function (node) {
      var id = node.getAttribute('data-routes');
      var marker = markersById[id];
      if (!marker || !marker.aedItem) return;
      var tmp = document.createElement('span');
      tmp.innerHTML = routesHtml(marker.aedItem.rec);
      node.replaceWith(tmp.firstChild || document.createTextNode(''));
    });
  }

  function runRouteQueue() {
    if (routes.busy || !routes.queue.length) return;
    var job = routes.queue.shift();
    if (pointKey(job.point) !== (state.point && pointKey(state.point))) return runRouteQueue(); // punkt się zmienił
    routes.busy = true;
    var wait = Math.max(0, routes.last + 1100 - Date.now());
    setTimeout(function () {
      routes.last = Date.now();
      var coords = [job.point].concat(job.recs).map(function (r) {
        return r.lon.toFixed(6) + ',' + r.lat.toFixed(6);
      }).join(';');
      fetchJson(ROUTES_URL + job.mode + '/table/v1/driving/' + coords + '?sources=0&annotations=distance')
        .then(function (json) {
          var straight = job.recs.map(function (r) { return Core.distanceKm(job.point, r); });
          return Core.parseOsrmTable(json, job.recs.length, straight);
        })
        .catch(function () {
          return null;
        })
        .then(function (dist) {
          job.recs.forEach(function (rec, i) {
            // null = brak wiarygodnej trasy, false = usługa nie odpowiedziała
            routes.cache[job.mode + '|' + pointKey(job.point) + '|' + rec.id_aed] = dist ? dist[i] : false;
          });
          routes.busy = false;
          paintRoutes();
          refreshOpenPopup();
          runRouteQueue();
        });
    }, wait);
  }

  /** Dokłada do kolejki AED bez policzonych tras (oba tryby). */
  function loadRoutes(items) {
    if (!state.point) return;
    var recs = [];
    items.forEach(function (item) {
      var rec = item.rec;
      if (rec.przyklad || recs.indexOf(rec) !== -1) return;
      if (routes.cache[routeKey('foot', rec)] !== undefined) return;
      if (routes.queue.some(function (j) { return j.recs.indexOf(rec) !== -1; })) return;
      recs.push(rec);
    });
    for (var i = 0; i < recs.length; i += ROUTES_MAX) {
      var chunk = recs.slice(i, i + ROUTES_MAX);
      routes.queue.push({ mode: 'foot', point: state.point, recs: chunk });
      routes.queue.push({ mode: 'car', point: state.point, recs: chunk });
    }
    runRouteQueue();
  }

  function refreshOpenPopup() {
    Object.keys(markersById).some(function (id) {
      var m = markersById[id];
      if (m.isPopupOpen && m.isPopupOpen()) {
        m.getPopup().setContent(popupHtml(m.aedItem));
        return true;
      }
      return false;
    });
  }

  function popupHtml(item) {
    var rec = item.rec;
    var parts = ['<h3>' + esc(rec.nazwa_obiektu || 'AED') + '</h3>'];
    if (Core.address(rec)) parts.push('<div>' + esc(Core.address(rec)) + '</div>');
    if (rec.opis_lokalizacji) parts.push('<div>' + esc(rec.opis_lokalizacji) + '</div>');
    parts.push(
      '<div class="row"><span class="badge badge-' + stateClass(item) + '">' +
        esc(rec.przyklad ? 'Przykład – fikcyjny' : item.availability.label) + '</span>' +
        (state.point ? '<span class="distance">' + esc(Core.formatDistance(item.km)) + '<span class="distance-note"> w linii prostej</span></span>' : '') + '</div>'
    );
    if (state.point && !rec.przyklad) parts.push('<div class="row">' + routesHtml(rec) + '</div>');
    if (!rec.przyklad) {
      parts.push('<div class="popup-verify">' + verifyTag(rec) +
        (rec.opis_weryfikacji ? '<span class="popup-meta">' + esc(rec.opis_weryfikacji) + '</span>' : '') + '</div>');
    }
    if (rec.dysponent_nazwa) parts.push('<div class="popup-meta">Dysponent: ' + esc(rec.dysponent_nazwa) + '</div>');
    if (rec.telefon_kontaktowy && !rec.przyklad) {
      parts.push('<div class="popup-meta">Telefon: <a href="tel:' + esc(rec.telefon_kontaktowy) + '">' + esc(rec.telefon_kontaktowy) + '</a></div>');
    }
    var photo = safeUrl(rec.zdjecie_url);
    if (photo) parts.push('<div class="popup-meta"><a href="' + esc(photo) + '" target="_blank" rel="noopener">Zdjęcie miejsca<span class="visually-hidden"> (nowa karta)</span></a></div>');
    parts.push('<div class="popup-meta">Źródło: ' + esc(rec.przyklad ? 'rekord przykładowy (fikcyjny)' : rec.zrodlo + ', ' + rec.licencja) + '</div>');
    var route = routeLink(rec, 'popup-route', 'Wyznacz trasę pieszo');
    if (route) parts.push('<p>' + route + '</p>');
    return parts.join('');
  }

  // Pinezki tworzymy raz i potem tylko aktualizujemy (ikona, przynależność do warstwy),
  // bo odświeżanie co minutę 18 tys. pinezek od zera byłoby za wolne na telefonie.
  var shownIds = [];
  var shownTop = null;

  function markerFor(item) {
    var rec = item.rec;
    var marker = markersById[rec.id_aed];
    if (!marker) {
      marker = L.marker([rec.lat, rec.lon], { keyboard: true, riseOnHover: true });
      marker.bindPopup(function () {
        return popupHtml(marker.aedItem);
      }, {
        autoPanPaddingTopLeft: [56, 16],
        autoPanPaddingBottomRight: [16, 16],
        maxWidth: Math.min(280, window.innerWidth - 150),
      });
      marker.on('click', function () {
        selectItem(rec.id_aed, false);
      });
      marker.on('popupopen', function () {
        loadRoutes([marker.aedItem]); // AED spoza listy – policz trasy przy otwarciu dymku
      });
      markersById[rec.id_aed] = marker;
    }
    marker.aedItem = item;
    return marker;
  }

  function renderMarkers(items, topId) {
    var ids = [];
    items.forEach(function (item) {
      var rec = item.rec;
      var marker = markerFor(item);
      var isTop = rec.id_aed === topId;
      var kind = stateClass(item);
      var key = kind + (isTop ? '|top' : '');
      if (marker.aedKey !== key) {
        var verified = Core.isVerified(rec);
        var title = (rec.nazwa_obiektu || 'AED') + ' – ' +
          (rec.przyklad ? 'przykład fikcyjny' : item.availability.label + ', ' + verifyLabel(rec).toLowerCase());
        marker.options.title = title;
        marker.options.alt = title;
        marker.setIcon(pinIcon(kind, isTop, verified)); // odtwarza element z nowym title/alt, jeśli jest na mapie
        marker.setZIndexOffset(isTop ? 1000 : 0);
        marker.aedKey = key;
      }
      ids.push(rec.id_aed);
    });
    var same = topId === shownTop && ids.length === shownIds.length;
    for (var i = 0; same && i < ids.length; i++) same = ids[i] === shownIds[i];
    if (same) return;
    shownIds = ids;
    shownTop = topId;
    clusterLayer.clearLayers();
    topLayer.clearLayers();
    var batch = [];
    ids.forEach(function (id) {
      if (id === topId) markersById[id].addTo(topLayer);
      else batch.push(markersById[id]);
    });
    if (clusterLayer.addLayers) clusterLayer.addLayers(batch);
    else batch.forEach(function (m) { m.addTo(clusterLayer); });
  }

  function showMe(point) {
    if (meMarker) meMarker.remove();
    if (radiusCircle) radiusCircle.remove();
    radiusCircle = L.circle([point.lat, point.lon], {
      radius: RADIUS_KM * 1000,
      color: '#0865c9',
      weight: 2,
      fillColor: '#0865c9',
      fillOpacity: 0.06,
      interactive: false,
    }).addTo(map);
    meMarker = L.marker([point.lat, point.lon], {
      icon: L.divIcon({ className: '', html: '<div class="me-marker"></div>', iconSize: [22, 22], iconAnchor: [11, 11] }),
      title: 'Twoje położenie',
      alt: 'Twoje położenie',
      keyboard: false,
      zIndexOffset: 2000,
    }).addTo(map);
  }

  function openMarker(id) {
    var marker = markersById[id];
    if (!marker) return;
    if (clusterLayer.hasLayer && clusterLayer.hasLayer(marker) && clusterLayer.zoomToShowLayer) {
      clusterLayer.zoomToShowLayer(marker, function () {
        marker.openPopup();
      });
    } else {
      map.once('moveend', function () {
        marker.openPopup();
      });
      map.setView(marker.getLatLng(), Math.max(map.getZoom(), 16), { animate: !reduceMotion });
    }
  }

  // --- Panel: wyróżnienie i lista ------------------------------------------

  function itemHtml(item) {
    var rec = item.rec;
    var cls = 'finder-item state-' + stateClass(item);
    return (
      '<li class="' + cls + '" data-id="' + esc(rec.id_aed) + '">' +
      '<button type="button" class="finder-item__btn" data-id="' + esc(rec.id_aed) + '">' +
      '<span class="finder-item__top">' +
      '<svg class="finder-item__aed" viewBox="0 0 50 50" aria-hidden="true" focusable="false"><rect width="50" height="50" fill="#1b7a43"/><path d="M22 41.5S8.5 33.6 8.5 23.6a7.6 7.6 0 0 1 13.5-4.8 7.6 7.6 0 0 1 13.5 4.8c0 10-13.5 17.9-13.5 17.9z" fill="#fff"/><path d="M24.4 20.2 18.6 29h4.4l-2 7.6 6.9-9.9h-4.6z" fill="#1b7a43"/></svg>' +
      '<span class="finder-item__state"><span class="dot dot-' + stateClass(item) + '" aria-hidden="true"></span>' +
      esc(rec.przyklad ? 'Przykład (fikcyjny) · ' + item.availability.label : item.availability.label) + '</span>' +
      verifyTag(rec) +
      '</span>' +
      '<span class="finder-item__addr">' + esc(where(rec)) + '</span>' +
      '<span class="finder-item__name">' + esc(rec.nazwa_obiektu || 'AED') + '</span>' +
      (state.point && !rec.przyklad ? '<span class="finder-item__routes">' + routesHtml(rec) + '</span>' : '') +
      (state.point ? '<span class="finder-item__dist">' + esc(Core.formatDistance(item.km)) +
        '<span class="visually-hidden"> w linii prostej</span><span class="finder-item__arrow" aria-hidden="true">▶</span></span>' : '') +
      '</button>' +
      '</li>'
    );
  }

  function renderHighlight(ranked) {
    var h = ranked.highlight;
    if (!h || !state.point) {
      el.highlight.hidden = true;
      return;
    }
    var rec = h.rec;
    var kicker = ranked.fallback ? 'Najbliższy AED – nie wiemy, czy jest teraz dostępny' : 'Najbliższy AED dostępny teraz';
    if (rec.przyklad) kicker = 'Przykład (fikcyjny) – ' + kicker.charAt(0).toLowerCase() + kicker.slice(1);
    var note = ranked.fallback
      ? '<p class="note">Brak godzin dostępności w danych. Jeśli ktoś nie oddycha – <a href="tel:112">dzwoń 112</a>.</p>'
      : '';
    el.highlight.className = 'highlight' + (ranked.fallback ? ' is-fallback' : '');
    el.highlight.innerHTML =
      '<p class="highlight-kicker">' + esc(kicker) + '</p>' +
      '<h3>' + esc(rec.nazwa_obiektu || 'AED') + '</h3>' +
      (where(rec) ? '<p class="meta">' + esc(where(rec)) + '</p>' : '') +
      '<div class="row"><span class="distance">' + esc(Core.formatDistance(h.km)) + '<span class="distance-note"> w linii prostej</span></span>' +
      routesHtml(rec) + '</div><div class="row">' +
      '<span class="badge badge-' + stateClass(h) + '">' + esc(h.availability.label) + '</span>' + verifyTag(rec) + '</div>' +
      (rec.opis_weryfikacji && !rec.przyklad ? '<p class="meta">' + esc(rec.opis_weryfikacji) + '</p>' : '') +
      '<div class="row">' + routeLink(rec, 'btn btn-primary btn-sm', 'Wyznacz trasę') +
      '<button type="button" class="btn btn-outline btn-sm" data-show="' + esc(rec.id_aed) + '">Pokaż na mapie</button></div>' +
      note;
    el.highlight.hidden = false;
  }

  function moreButton(shown, total) {
    if (shown >= total) return '';
    var next = Math.min(LIST_PAGE, total - shown);
    return '<li class="finder-more"><button type="button" class="btn btn-outline btn-sm" data-more="1">' +
      'Pokaż kolejne ' + next + ' (z ' + (total - shown) + ' pozostałych)</button></li>';
  }

  function renderList(ranked) {
    if (!state.point) {
      var all = ranked.list.filter(function (item) {
        return !state.onlyAvailable || item.availability.state === 'dostepny';
      });
      // Bez lokalizacji nie układamy listy 18 tys. pozycji – tylko podsumowanie (mapa pokazuje wszystkie).
      el.listSummary.innerHTML =
        '<strong>Wyniki:</strong> ' + all.length.toLocaleString('pl-PL') + ' AED w bazie – wskaż lokalizację, aby zobaczyć te w promieniu ' + RADIUS_KM + ' km';
      el.list.innerHTML = '';
      return [];
    }
    var res = Core.inRadius(ranked.list, RADIUS_KM, state.onlyAvailable);
    el.listSummary.innerHTML = '<strong>Wyniki:</strong> ' + res.items.length + ' w promieniu ' + RADIUS_KM + ' km' +
      '<span class="finder-summary__note">Po prawej odległość w linii prostej, pod nazwą – po drogach: pieszo i samochodem.</span>';
    var visible = res.items.slice(0, state.listLimit);
    var html = visible.map(itemHtml).join('') + moreButton(visible.length, res.items.length);
    if (!res.items.length) {
      var msg = state.onlyAvailable
        ? 'Brak AED oznaczonych jako dostępne teraz w promieniu ' + RADIUS_KM + ' km.'
        : 'Brak AED w promieniu ' + RADIUS_KM + ' km.';
      if (res.nearestOutside) {
        msg += ' Najbliższy: ' + Core.formatDistance(res.nearestOutside.km) + ' stąd.';
      }
      html = '<li class="finder-empty">' + esc(msg) + '</li>' + (res.nearestOutside ? itemHtml(res.nearestOutside) : '');
    }
    el.list.innerHTML = html;
    return res.items.length ? visible : res.nearestOutside ? [res.nearestOutside] : [];
  }

  function render() {
    var now = new Date();
    var point = state.point || { lat: POLAND.center[0], lon: POLAND.center[1] };
    var ranked = Core.rank(records(), point, now);
    state.ranked = ranked;
    var shown = renderList(ranked);
    renderHighlight(ranked);
    if (state.point) loadRoutes((ranked.highlight ? [ranked.highlight] : []).concat(shown));
    // Na mapie zawsze wszystkie AED (z filtrem „dostępne teraz”); lista – w promieniu.
    var onMap = ranked.list.filter(function (item) {
      return !state.onlyAvailable || item.availability.state === 'dostepny';
    });
    renderMarkers(onMap, state.point && ranked.highlight ? ranked.highlight.rec.id_aed : null);
    return ranked;
  }

  function selectItem(id, moveMap) {
    state.selectedId = id;
    Array.prototype.forEach.call(el.list.querySelectorAll('.finder-item'), function (li) {
      li.classList.toggle('is-selected', li.getAttribute('data-id') === id);
    });
    if (moveMap) openMarker(id);
  }

  // --- Ustalanie położenia ---------------------------------------------------

  function fitAll() {
    var recs = records();
    if (!recs.length) return;
    map.fitBounds(L.latLngBounds(recs.map(function (r) { return [r.lat, r.lon]; })), { padding: [32, 32], maxZoom: 13, animate: false });
  }

  function setPoint(point, via) {
    state.point = point;
    state.listLimit = LIST_PAGE;
    showMe(point);
    var ranked = render();
    var h = ranked.highlight;
    var bounds = radiusCircle.getBounds();
    if (h && h.km > RADIUS_KM && h.km < 300) bounds.extend([h.rec.lat, h.rec.lon]);
    if (map.getContainer().offsetWidth > 900) {
      map.fitBounds(bounds, { paddingTopLeft: [460, 24], paddingBottomRight: [24, 24], animate: !reduceMotion });
    } else {
      map.fitBounds(bounds, { padding: [16, 16], animate: !reduceMotion });
    }
    if (h) {
      var msg = ranked.fallback
        ? 'Żaden AED nie ma w danych godzin dostępności – wyróżniamy najbliższy: ' + (h.rec.nazwa_obiektu || 'AED') + ', ' + Core.formatDistance(h.km)
        : 'Najbliższy AED dostępny teraz: ' + (h.rec.nazwa_obiektu || 'AED') + ', ' + Core.formatDistance(h.km);
      msg += h.rec.przyklad ? ' – UWAGA: rekord przykładowy (fikcyjny).' : ' (' + verifyLabel(h.rec).toLowerCase() + ').';
      setStatus('Szukamy wokół: ' + point.label + '. ' + msg, ranked.fallback);
    }
    if (via === 'geo' || via === 'search') {
      el.listSummary.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'nearest' });
    }
  }

  function locate() {
    if (!('geolocation' in navigator)) {
      geoFailed('Twoja przeglądarka nie udostępnia lokalizacji.');
      return;
    }
    el.locate.setAttribute('aria-busy', 'true');
    el.locate.disabled = true;
    setStatus('Ustalamy Twoją lokalizację…');
    navigator.geolocation.getCurrentPosition(
      function (pos) {
        resetButton();
        setPoint({ lat: pos.coords.latitude, lon: pos.coords.longitude, label: 'Twoja lokalizacja' }, 'geo');
      },
      function (err) {
        resetButton();
        geoFailed(
          err && err.code === 1
            ? 'Nie mamy zgody na dostęp do lokalizacji.'
            : err && err.code === 3
              ? 'Ustalanie lokalizacji trwało zbyt długo.'
              : 'Nie udało się ustalić lokalizacji.'
        );
      },
      { enableHighAccuracy: true, timeout: 12000, maximumAge: 60000 }
    );
  }

  function resetButton() {
    el.locate.removeAttribute('aria-busy');
    el.locate.disabled = false;
  }

  function geoFailed(reason) {
    setStatus(reason + ' Wpisz adres lub miejscowość w polu wyszukiwania albo kliknij na mapie miejsce, w którym jesteś.', true);
    el.search.focus();
  }

  // --- Wyszukiwanie adresu: nasze miejscowości → Nominatim (OSM) → GUGiK ----

  function fetchJson(url) {
    return fetch(url, { headers: { Accept: 'application/json' } }).then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    });
  }

  function geocode(query) {
    var local = Core.matchCity(records(), query);
    if (local) return Promise.resolve(local);
    var q = encodeURIComponent(query);
    return fetchJson('https://nominatim.openstreetmap.org/search?format=jsonv2&countrycodes=pl&limit=1&accept-language=pl&q=' + q)
      .then(Core.parseNominatim)
      .catch(function () {
        return null;
      })
      .then(function (hit) {
        if (hit) return hit;
        return fetchJson('https://services.gugik.gov.pl/uug/?request=GetAddress&srid=4326&address=' + q)
          .then(Core.parseGugik)
          .catch(function () {
            return null;
          });
      });
  }

  // --- Podpowiedzi adresu (combobox wg WAI-ARIA APG) -----------------------
  // Źródło: Photon (komoot, dane OSM) – usługa do wyszukiwania w trakcie pisania.
  // Nominatim zabrania autouzupełniania, dlatego używamy go tylko po zatwierdzeniu (Enter).
  // Zapytanie wysyłamy po przerwie w pisaniu (debounce), od 3 znaków, z pamięcią wyników.

  var SUGGEST_MIN = 3;
  var SUGGEST_DELAY = 350;
  var PHOTON = 'https://photon.komoot.io/api/?limit=10&bbox=14.07,49.0,24.15,54.84';
  var suggest = {
    box: document.getElementById('search-suggest'),
    live: document.getElementById('suggest-status'),
    items: [],
    active: -1,
    timer: null,
    seq: 0,
    cache: {},
  };

  function highlightHtml(text, query) {
    return Core.matchParts(text, query).map(function (part) {
      return part.match ? '<mark>' + esc(part.text) + '</mark>' : esc(part.text);
    }).join('');
  }

  function closeSuggest() {
    suggest.box.hidden = true;
    suggest.box.innerHTML = '';
    suggest.items = [];
    suggest.active = -1;
    el.search.setAttribute('aria-expanded', 'false');
    el.search.removeAttribute('aria-activedescendant');
  }

  function setActive(index) {
    var nodes = suggest.box.querySelectorAll('.suggest__item');
    if (!nodes.length) return;
    if (index < 0) index = nodes.length - 1;
    if (index >= nodes.length) index = 0;
    suggest.active = index;
    Array.prototype.forEach.call(nodes, function (n, i) {
      var on = i === index;
      n.classList.toggle('is-active', on);
      n.setAttribute('aria-selected', String(on));
    });
    el.search.setAttribute('aria-activedescendant', nodes[index].id);
    nodes[index].scrollIntoView({ block: 'nearest' });
  }

  function showSuggest(items, query) {
    suggest.items = items;
    suggest.active = -1;
    el.search.removeAttribute('aria-activedescendant');
    if (!items.length) {
      suggest.box.innerHTML = '<li class="suggest__note" role="presentation">Brak podpowiedzi – naciśnij Enter, aby wyszukać „' + esc(query) + '”.</li>';
      suggest.live.textContent = 'Brak podpowiedzi.';
    } else {
      suggest.box.innerHTML = items.map(function (it, i) {
        return '<li id="suggest-' + i + '" class="suggest__item" role="option" aria-selected="false" data-index="' + i + '">' +
          '<span class="suggest__label">' + highlightHtml(it.label, query) + '</span>' +
          (it.sub ? '<span class="suggest__sub">' + highlightHtml(it.sub, query) + '</span>' : '') +
          '</li>';
      }).join('');
      suggest.live.textContent = items.length + (items.length === 1 ? ' podpowiedź' : ' podpowiedzi') +
        '. Wybierz strzałkami w dół i w górę.';
    }
    suggest.box.hidden = false;
    el.search.setAttribute('aria-expanded', 'true');
  }

  function photonUrl(query) {
    var url = PHOTON + '&q=' + encodeURIComponent(query);
    // Przy wskazanym punkcie lub przybliżonej mapie – wyżej podpowiedzi z okolicy.
    var c = state.point || (map && map.getZoom() >= 9 ? { lat: map.getCenter().lat, lon: map.getCenter().lng } : null);
    if (c) url += '&lat=' + c.lat.toFixed(4) + '&lon=' + c.lon.toFixed(4);
    return url;
  }

  function requestSuggest() {
    var query = el.search.value.trim();
    clearTimeout(suggest.timer);
    if (query.length < SUGGEST_MIN) {
      closeSuggest();
      return;
    }
    var seq = ++suggest.seq;
    suggest.timer = setTimeout(function () {
      var url = photonUrl(query);
      var cached = suggest.cache[url];
      var p = cached ? Promise.resolve(cached) : fetchJson(url).then(function (json) {
        var items = Core.parsePhoton(json, 6);
        suggest.cache[url] = items;
        return items;
      });
      p.then(function (items) {
        // Odpowiedź na stare zapytanie albo pole już bez fokusu – pomijamy.
        if (seq !== suggest.seq || document.activeElement !== el.search) return;
        showSuggest(items, query);
      }).catch(function () {
        if (seq === suggest.seq) closeSuggest(); // bez podpowiedzi zostaje zwykłe wyszukiwanie (Enter)
      });
    }, SUGGEST_DELAY);
  }

  function chooseSuggest(index) {
    var it = suggest.items[index];
    if (!it) return;
    var text = it.label + (it.sub ? ', ' + it.sub : '');
    el.search.value = text;
    suggest.seq++;
    closeSuggest();
    setStatus('Szukamy wokół: ' + text + '…');
    setPoint({ lat: it.lat, lon: it.lon, label: text }, 'search');
  }

  el.search.addEventListener('input', requestSuggest);

  el.search.addEventListener('keydown', function (e) {
    var open = !suggest.box.hidden && suggest.items.length;
    if (e.key === 'ArrowDown') {
      if (!open) return requestSuggest();
      e.preventDefault();
      setActive(suggest.active + 1);
    } else if (e.key === 'ArrowUp') {
      if (!open) return;
      e.preventDefault();
      setActive(suggest.active - 1);
    } else if (e.key === 'Enter' && open && suggest.active >= 0) {
      e.preventDefault();
      chooseSuggest(suggest.active);
    } else if (e.key === 'Escape' && !suggest.box.hidden) {
      e.preventDefault();
      suggest.seq++;
      closeSuggest();
    }
  });

  el.search.addEventListener('blur', function () {
    // Kliknięcie w podpowiedź obsługuje mousedown (przed blur), więc tu tylko zamykamy.
    suggest.seq++;
    closeSuggest();
  });

  suggest.box.addEventListener('mousedown', function (e) {
    var item = e.target.closest ? e.target.closest('.suggest__item') : null;
    e.preventDefault(); // fokus zostaje w polu
    if (item) chooseSuggest(Number(item.getAttribute('data-index')));
  });

  el.form.addEventListener('submit', function (e) {
    e.preventDefault();
    suggest.seq++;
    closeSuggest();
    var query = el.search.value.trim();
    if (!query) {
      setStatus('Wpisz adres, miejscowość lub nazwę miejsca.', true);
      el.search.focus();
      return;
    }
    setStatus('Szukamy: ' + query + '…');
    el.form.setAttribute('aria-busy', 'true');
    geocode(query).then(function (hit) {
      el.form.removeAttribute('aria-busy');
      if (!hit) {
        setStatus('Nie znaleźliśmy „' + query + '”. Spróbuj wpisać miejscowość i ulicę, np. „Krosno, Lwowska 28”.', true);
        return;
      }
      setPoint({ lat: hit.lat, lon: hit.lon, label: query }, 'search');
    });
  });

  // --- Dane i stopka -------------------------------------------------------

  function renderDataInfo() {
    var n = DATA.aed.length;
    var verified = DATA.aed.filter(Core.isVerified).length;
    var withHours = DATA.aed.filter(function (r) { return !!Core.parseOpeningHours(r.godziny_dostepnosci); }).length;
    var fmt = function (x) { return x.toLocaleString('pl-PL'); };
    el.dataSummary.textContent =
      'Na mapie jest ' + fmt(n) + ' AED: ' + fmt(verified) + ' zweryfikowanych (dane instytucji opublikowane na dane.gov.pl) i ' +
      fmt(n - verified) + ' niezweryfikowanych (dane społeczne z OpenStreetMap, przez OpenAEDMap). ' +
      'Godziny dostępności podaje ' + fmt(withHours) + ' z ' + fmt(n) + '. ' +
      'Dane zbudowano: ' + new Date(DATA.wygenerowano).toLocaleString('pl-PL') + '.';
    el.sources.innerHTML = DATA.zrodla.map(function (s) {
      var url = safeUrl(s.url);
      var name = esc(s.nazwa || s.id) + ' – ' + esc(s.dysponent);
      var osm = s.licencja === 'ODbL-1.0'
        ? ' (© autorzy <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>, ' +
          '<a href="https://opendatacommons.org/licenses/odbl/1-0/">ODbL 1.0</a>)'
        : ', licencja ' + esc(s.licencja);
      return '<li>' + (url ? '<a href="' + esc(url) + '">' + name + '</a>' : name) + osm + '</li>';
    }).join('');
  }

  // --- Zdarzenia -------------------------------------------------------------

  el.locate.addEventListener('click', locate);

  Array.prototype.forEach.call(el.tabs, function (tab) {
    tab.addEventListener('click', function () {
      state.onlyAvailable = tab.getAttribute('data-filter') === 'available';
      Array.prototype.forEach.call(el.tabs, function (t) {
        t.setAttribute('aria-pressed', String(t === tab));
      });
      render();
    });
  });

  el.showExamples.addEventListener('change', function () {
    state.showExamples = el.showExamples.checked;
    if (state.point) {
      setPoint(state.point, 'map');
    } else {
      render();
      fitAll();
    }
  });

  el.list.addEventListener('click', function (e) {
    var more = e.target.closest ? e.target.closest('[data-more]') : null;
    if (!more) return;
    var focusIndex = state.listLimit; // fokus na pierwszy dołożony wynik (klawiatura, czytnik ekranu)
    state.listLimit += LIST_PAGE;
    render();
    var btns = el.list.querySelectorAll('.finder-item__btn');
    if (btns[focusIndex]) btns[focusIndex].focus();
  });

  document.addEventListener('click', function (e) {
    var target = e.target.closest ? e.target.closest('.finder-item__btn, [data-show]') : null;
    if (!target) return;
    var id = target.getAttribute('data-id') || target.getAttribute('data-show');
    selectItem(id, true);
    if (window.innerWidth < 992) {
      document.getElementById('map').scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'center' });
    }
  });

  setInterval(function () {
    if (state.point) render(); // „dostępny teraz” zmienia się z upływem czasu
  }, 60000);

  // --- Start: od razu mapa ze wszystkimi AED --------------------------------

  initMap();
  renderDataInfo();
  render();
  fitAll();
})();
