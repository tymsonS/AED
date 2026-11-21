/*
 * Znajdź AED – interfejs. Logika (odległości, godziny, ranking) jest w aed-core.js.
 * Dane: window.AED_DATA z data/aed-data.js (generuje app/scripts/build_data.py).
 * Teksty z danych źródłowych wstawiamy wyłącznie jako tekst (textContent / esc()).
 */
(function () {
  'use strict';

  var Core = window.AedCore;
  var DATA = window.AED_DATA || { aed: [], przyklady: [], zrodla: [] };
  var POLAND = { center: [52.1, 19.4], zoom: 6 };
  var FAR_KM = 30;
  var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  var state = {
    point: null, // { lat, lon, label }
    showExamples: false,
    onlyAvailable: false,
    selectedId: null,
    ranked: null,
  };

  var el = {
    locate: document.getElementById('locate'),
    place: document.getElementById('place'),
    status: document.getElementById('status'),
    results: document.getElementById('wyniki'),
    highlight: document.getElementById('highlight'),
    list: document.getElementById('list'),
    listSummary: document.getElementById('list-summary'),
    onlyAvailable: document.getElementById('only-available'),
    showExamples: document.getElementById('show-examples'),
    dataSummary: document.getElementById('data-summary'),
    sources: document.getElementById('sources'),
  };

  var map = null;
  var markerLayer = null;
  var meMarker = null;
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

  function routeUrl(from, rec) {
    return Core.routeUrl(from, rec);
  }

  function setStatus(text, warning) {
    el.status.textContent = text;
    el.status.classList.toggle('is-warning', !!warning);
  }

  function stateClass(item) {
    return item.rec.przyklad ? 'przyklad' : item.availability.state;
  }

  // --- Mapa ------------------------------------------------------------------

  var PIN_COLORS = {
    dostepny: '#1e7b34',
    nieznany: '#5e5e5e',
    niedostepny: '#a91e2c',
    przyklad: '#8a6a00',
  };

  function pinIcon(kind, top) {
    var color = PIN_COLORS[kind];
    var svg =
      '<svg viewBox="0 0 30 40" aria-hidden="true" focusable="false">' +
      '<path d="M15 39s13-14.4 13-24A13 13 0 0 0 2 15c0 9.6 13 24 13 24z" fill="' + color + '" stroke="#fff" stroke-width="2"' +
      (kind === 'przyklad' ? ' stroke-dasharray="3 2"' : '') + '/>' +
      '<path d="M15 23s-6-3.6-6-8.2A3.5 3.5 0 0 1 15 12.4a3.5 3.5 0 0 1 6 2.4c0 4.6-6 8.2-6 8.2z" fill="#fff"/>' +
      '<path d="M15.6 13.6 13.4 17h1.7l-.7 2.7 2.6-3.6h-1.8z" fill="' + color + '"/>' +
      '</svg>';
    var size = top ? [44, 58] : [30, 40];
    return L.divIcon({
      className: 'pin' + (top ? ' is-top' : ''),
      html: svg,
      iconSize: size,
      iconAnchor: [size[0] / 2, size[1]],
      popupAnchor: [0, -size[1] + 6],
    });
  }

  function initMap() {
    if (map) return;
    map = L.map('map', { zoomControl: true, scrollWheelZoom: true }).setView(POLAND.center, POLAND.zoom);
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; autorzy <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(map);
    markerLayer = L.layerGroup().addTo(map);
    map.on('click', function (e) {
      setPoint({ lat: e.latlng.lat, lon: e.latlng.lng, label: 'wskazany punkt na mapie' }, 'map');
    });
  }

  function popupHtml(item) {
    var rec = item.rec;
    var parts = ['<h3>' + esc(rec.nazwa_obiektu || 'AED') + '</h3>'];
    parts.push('<div>' + esc(Core.address(rec)) + '</div>');
    if (rec.opis_lokalizacji) parts.push('<div>' + esc(rec.opis_lokalizacji) + '</div>');
    parts.push(
      '<div class="row"><span class="badge badge-' + stateClass(item) + '">' +
        esc(rec.przyklad ? 'Przykład – fikcyjny' : item.availability.label) + '</span>' +
        (state.point ? '<span class="distance">' + esc(Core.formatDistance(item.km)) + '</span>' : '') +
        '</div>'
    );
    if (state.point && !rec.przyklad) {
      parts.push(
        '<p><a href="' + esc(routeUrl(state.point, rec)) + '" target="_blank" rel="noopener">Wyznacz trasę pieszo<span class="visually-hidden"> (otwiera się w nowej karcie)</span></a></p>'
      );
    }
    return parts.join('');
  }

  function renderMarkers(items, topId) {
    markerLayer.clearLayers();
    markersById = {};
    items.forEach(function (item) {
      var rec = item.rec;
      var isTop = rec.id_aed === topId;
      var title = (rec.nazwa_obiektu || 'AED') + ' – ' + (rec.przyklad ? 'przykład fikcyjny' : item.availability.label);
      var marker = L.marker([rec.lat, rec.lon], {
        icon: pinIcon(stateClass(item), isTop),
        title: title,
        alt: title,
        keyboard: true,
        zIndexOffset: isTop ? 1000 : rec.przyklad ? -100 : 0,
        riseOnHover: true,
      });
      marker.bindPopup(popupHtml(item), { autoPanPaddingTopLeft: [56, 16], autoPanPaddingBottomRight: [16, 16], maxWidth: Math.min(280, window.innerWidth - 150) });
      marker.on('click', function () {
        selectItem(rec.id_aed, false);
      });
      marker.addTo(markerLayer);
      markersById[rec.id_aed] = marker;
    });
  }

  function showMe(point) {
    if (meMarker) meMarker.remove();
    meMarker = L.marker([point.lat, point.lon], {
      icon: L.divIcon({ className: '', html: '<div class="me-marker"></div>', iconSize: [22, 22], iconAnchor: [11, 11] }),
      title: 'Twoje położenie',
      alt: 'Twoje położenie',
      keyboard: false,
      zIndexOffset: 2000,
    }).addTo(map);
  }

  // --- Lista i wyróżnienie --------------------------------------------------

  function itemHtml(item) {
    var rec = item.rec;
    var cls = 'aed-item state-' + item.availability.state + (rec.przyklad ? ' is-example' : '');
    var details = [];
    if (rec.opis_lokalizacji) details.push(['Gdzie dokładnie', esc(rec.opis_lokalizacji)]);
    if (rec.dysponent_nazwa) details.push(['Dysponent', esc(rec.dysponent_nazwa)]);
    if (rec.telefon_kontaktowy && !rec.przyklad) {
      details.push(['Telefon', '<a href="tel:' + esc(rec.telefon_kontaktowy) + '">' + esc(rec.telefon_kontaktowy) + '</a>']);
    }
    var photo = safeUrl(rec.zdjecie_url);
    if (photo) {
      details.push(['Zdjęcie', '<a href="' + esc(photo) + '" target="_blank" rel="noopener">zobacz zdjęcie miejsca<span class="visually-hidden"> (otwiera się w nowej karcie)</span></a>']);
    }
    details.push(['Źródło', esc(rec.przyklad ? 'rekord przykładowy ze wzorcowego zakresu danych (fikcyjny)' : rec.zrodlo + ', ' + rec.licencja)]);

    var route = state.point && !rec.przyklad
      ? '<a class="btn btn-outline btn-sm" href="' + esc(routeUrl(state.point, rec)) + '" target="_blank" rel="noopener">Wyznacz trasę<span class="visually-hidden"> do ' + esc(rec.nazwa_obiektu) + ' (otwiera się w nowej karcie)</span></a>'
      : '';

    return (
      '<li class="' + cls + '" data-id="' + esc(rec.id_aed) + '">' +
      '<div class="aed-main">' +
      '<h3><button type="button" class="aed-select" data-id="' + esc(rec.id_aed) + '">' + esc(rec.nazwa_obiektu || 'AED') + '</button></h3>' +
      '<p class="meta">' + esc(Core.address(rec)) + '</p>' +
      (rec.przyklad ? '<div class="row"><span class="badge badge-przyklad">Przykład – fikcyjny</span></div>' : '') +
      '<dl class="details">' +
      details.map(function (d) { return '<dt>' + d[0] + '</dt><dd>' + d[1] + '</dd>'; }).join('') +
      '</dl>' +
      '</div>' +
      '<div class="aed-side">' +
      (state.point ? '<p class="side-line"><strong>Odległość:</strong> <span class="distance">' + esc(Core.formatDistance(item.km)) + '</span></p>' : '') +
      '<p class="side-line"><strong>Dostępność:</strong></p>' +
      '<p class="side-line"><span class="badge badge-' + item.availability.state + '">' + esc(item.availability.label) + '</span></p>' +
      (route ? '<div class="row">' + route + '</div>' : '') +
      '</div>' +
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
    var note = '';
    if (ranked.fallback) {
      note =
        '<p class="note">W danych żadnego AED w pobliżu nie ma godzin dostępności, więc nie możemy potwierdzić, że ten jest teraz otwarty. ' +
        'Jeśli ktoś stracił przytomność i nie oddycha – <a href="tel:112">dzwoń 112</a>.</p>';
    }
    if (h.km > FAR_KM && !rec.przyklad) {
      note +=
        '<p class="note">Najbliższy AED w naszych danych jest ' + esc(Core.formatDistance(h.km)) +
        ' stąd. Prototyp zawiera na razie tylko zbiory z dane.gov.pl dla Przemyśla, Krosna i Marek.</p>';
    }
    el.highlight.className = 'highlight' + (ranked.fallback ? ' is-fallback' : '');
    el.highlight.innerHTML =
      '<p class="highlight-kicker">' + esc(kicker) + '</p>' +
      '<h3>' + esc(rec.nazwa_obiektu || 'AED') + '</h3>' +
      '<p class="meta">' + esc(Core.address(rec)) + (rec.opis_lokalizacji ? ' · ' + esc(rec.opis_lokalizacji) : '') + '</p>' +
      '<div class="row"><span class="distance">' + esc(Core.formatDistance(h.km)) + '</span>' +
      '<span class="badge badge-' + stateClass(h) + '">' + esc(rec.przyklad ? 'Przykład – fikcyjny · ' + h.availability.label : h.availability.label) + '</span></div>' +
      '<div class="row">' +
      (rec.przyklad ? '' : '<a class="btn btn-primary" href="' + esc(routeUrl(state.point, rec)) + '" target="_blank" rel="noopener">Wyznacz trasę pieszo<span class="visually-hidden"> (otwiera się w nowej karcie)</span></a>') +
      '<button type="button" class="btn btn-outline" data-show="' + esc(rec.id_aed) + '">Pokaż na mapie</button>' +
      '</div>' + note;
    el.highlight.hidden = false;
  }

  function renderList(ranked) {
    var items = ranked.list.filter(function (item) {
      return !state.onlyAvailable || item.availability.state === 'dostepny';
    });
    el.list.innerHTML = items.map(itemHtml).join('');
    var total = ranked.list.length;
    if (state.onlyAvailable && !items.length) {
      el.listSummary.textContent = 'Brak AED oznaczonych jako dostępne teraz. W danych brakuje godzin dostępności – wyłącz filtr, aby zobaczyć wszystkie.';
    } else if (state.point) {
      el.listSummary.innerHTML = '<strong>Znaleziono:</strong> AED (' + items.length + (items.length !== total ? ' z ' + total : '') + ') · od najbliższego, względem: ' + esc(state.point.label);
    } else {
      el.listSummary.innerHTML = '<strong>Znaleziono:</strong> AED (' + items.length + ') · użyj „Znajdź AED”, aby posortować od najbliższego';
    }
    return items;
  }

  function render() {
    var now = new Date();
    var point = state.point || { lat: POLAND.center[0], lon: POLAND.center[1] };
    var ranked = Core.rank(records(), point, now);
    if (!state.point) {
      ranked.list.sort(function (a, b) {
        return String(a.rec.miejscowosc).localeCompare(String(b.rec.miejscowosc), 'pl') ||
          String(a.rec.nazwa_obiektu).localeCompare(String(b.rec.nazwa_obiektu), 'pl');
      });
    }
    state.ranked = ranked;
    var items = renderList(ranked);
    renderHighlight(ranked);
    renderMarkers(items, state.point && ranked.highlight ? ranked.highlight.rec.id_aed : null);
    return ranked;
  }

  function selectItem(id, moveMap) {
    state.selectedId = id;
    Array.prototype.forEach.call(el.list.querySelectorAll('.aed-item'), function (li) {
      li.classList.toggle('is-selected', li.getAttribute('data-id') === id);
    });
    var marker = markersById[id];
    if (marker && moveMap) {
      map.once('moveend', function () {
        marker.openPopup();
      });
      map.setView(marker.getLatLng(), Math.max(map.getZoom(), 16), { animate: !reduceMotion });
    }
  }

  // --- Ustalanie położenia -------------------------------------------------

  function showResults() {
    el.results.hidden = false;
    initMap();
    map.invalidateSize();
  }

  function setPoint(point, via) {
    state.point = point;
    showResults();
    showMe(point);
    var ranked = render();
    var h = ranked.highlight;
    if (h) {
      var bounds = L.latLngBounds([[point.lat, point.lon], [h.rec.lat, h.rec.lon]]);
      ranked.list.slice(0, 5).forEach(function (item) {
        if (item.km <= Math.max(h.km * 1.5, 2)) bounds.extend([item.rec.lat, item.rec.lon]);
      });
      var top = markersById[h.rec.id_aed];
      if (top) {
        map.once('moveend', function () {
          top.openPopup();
        });
      }
      map.fitBounds(bounds, { padding: [48, 48], maxZoom: 17, animate: !reduceMotion });
      var msg = ranked.fallback
        ? 'Znaleziono ' + ranked.list.length + ' AED. Żaden nie ma w danych godzin dostępności – wyróżniamy najbliższy: ' +
          (h.rec.nazwa_obiektu || 'AED') + ', ' + Core.formatDistance(h.km) + '.'
        : 'Najbliższy AED dostępny teraz: ' + (h.rec.nazwa_obiektu || 'AED') + ', ' + Core.formatDistance(h.km) +
          (h.rec.przyklad ? ' – UWAGA: to rekord przykładowy (fikcyjny), włączony w filtrach.' : '.');
      setStatus(msg, ranked.fallback);
    }
    if (via !== 'map') {
      el.results.focus({ preventScroll: true });
      el.results.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'start' });
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
        var reason =
          err && err.code === 1
            ? 'Nie mamy zgody na dostęp do lokalizacji.'
            : err && err.code === 3
              ? 'Ustalanie lokalizacji trwało zbyt długo.'
              : 'Nie udało się ustalić lokalizacji.';
        geoFailed(reason);
      },
      { enableHighAccuracy: true, timeout: 12000, maximumAge: 60000 }
    );
  }

  function resetButton() {
    el.locate.removeAttribute('aria-busy');
    el.locate.disabled = false;
  }

  function geoFailed(reason) {
    showResults();
    render();
    setStatus(reason + ' Wybierz miejscowość z listy albo kliknij na mapie miejsce, w którym jesteś.', true);
    el.place.focus();
  }

  function cityCenters() {
    var acc = {};
    records().forEach(function (r) {
      if (!r.miejscowosc) return;
      var key = r.miejscowosc + (r.przyklad ? ' (przykład)' : '');
      acc[key] = acc[key] || { lat: 0, lon: 0, n: 0 };
      acc[key].lat += r.lat;
      acc[key].lon += r.lon;
      acc[key].n += 1;
    });
    return Object.keys(acc)
      .sort(function (a, b) { return a.localeCompare(b, 'pl'); })
      .map(function (k) { return { name: k, lat: acc[k].lat / acc[k].n, lon: acc[k].lon / acc[k].n }; });
  }

  function fillPlaces() {
    var current = el.place.value;
    el.place.innerHTML = '<option value="">— wybierz —</option>' +
      cityCenters().map(function (c) {
        return '<option value="' + esc(c.lat + ',' + c.lon) + '">' + esc(c.name) + '</option>';
      }).join('');
    el.place.value = current;
  }

  // --- Dane i stopka -------------------------------------------------------

  function renderDataInfo() {
    var n = DATA.aed.length;
    var withHours = DATA.aed.filter(function (r) { return !!Core.parseOpeningHours(r.godziny_dostepnosci); }).length;
    var nSources = DATA.zrodla.length;
    el.dataSummary.textContent =
      'Na mapie jest ' + n + ' AED z ' + nSources + ' zbiorów opublikowanych na dane.gov.pl. ' +
      'Godziny dostępności podaje ' + withHours + ' z ' + n + '. ' +
      'Dane zbudowano: ' + new Date(DATA.wygenerowano).toLocaleString('pl-PL') + '.';
    el.sources.innerHTML = DATA.zrodla.map(function (s) {
      var url = safeUrl(s.url);
      var name = esc(s.nazwa || s.id) + ' – ' + esc(s.dysponent);
      return '<li>' + (url ? '<a href="' + esc(url) + '">' + name + '</a>' : name) + ', licencja ' + esc(s.licencja) + '</li>';
    }).join('');
  }

  // --- Zdarzenia -------------------------------------------------------------

  el.locate.addEventListener('click', locate);

  el.place.addEventListener('change', function () {
    if (!el.place.value) return;
    var parts = el.place.value.split(',');
    var label = el.place.options[el.place.selectedIndex].textContent;
    setPoint({ lat: Number(parts[0]), lon: Number(parts[1]), label: 'centrum: ' + label }, 'place');
  });

  el.onlyAvailable.addEventListener('change', function () {
    state.onlyAvailable = el.onlyAvailable.checked;
    if (map) render();
  });

  el.showExamples.addEventListener('change', function () {
    state.showExamples = el.showExamples.checked;
    fillPlaces();
    if (state.point) {
      setPoint(state.point, 'map');
    } else if (map) {
      render();
    }
  });

  document.addEventListener('click', function (e) {
    var target = e.target.closest ? e.target.closest('[data-id].aed-select, [data-show]') : null;
    if (!target) return;
    var id = target.getAttribute('data-id') || target.getAttribute('data-show');
    selectItem(id, true);
    document.getElementById('map').scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'center' });
  });

  setInterval(function () {
    if (state.point) render(); // „dostępny teraz” zmienia się z upływem czasu
  }, 60000);

  // --- Start ---------------------------------------------------------------------

  el.results.hidden = true;
  fillPlaces();
  renderDataInfo();
})();
