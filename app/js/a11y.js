/*
 * Przełączniki dostępności jak w dane.gov.pl: 4 tryby kontrastu, 4 wielkości tekstu
 * (100/125/150/200%), menu na telefonie. Wybór zapamiętujemy w localStorage tej przeglądarki.
 */
(function () {
  'use strict';

  var root = document.documentElement;

  function save(key, value) {
    try {
      if (value) localStorage.setItem(key, value);
      else localStorage.removeItem(key);
    } catch (e) {
      /* tryb prywatny / brak dostępu – ustawienie działa do odświeżenia strony */
    }
  }

  function sync(attr, selector) {
    var current = root.getAttribute(attr) || '';
    Array.prototype.forEach.call(document.querySelectorAll(selector), function (btn) {
      btn.setAttribute('aria-pressed', String((btn.getAttribute(attr) || '') === current));
    });
  }

  function bind(attr, selector, storageKey) {
    Array.prototype.forEach.call(document.querySelectorAll(selector), function (btn) {
      btn.addEventListener('click', function () {
        var value = btn.getAttribute(attr) || '';
        if (value) root.setAttribute(attr, value);
        else root.removeAttribute(attr);
        save(storageKey, value);
        sync(attr, selector);
        window.dispatchEvent(new Event('resize')); // mapa przelicza rozmiar po zmianie czcionki
      });
    });
    sync(attr, selector);
  }

  bind('data-contrast', 'button[data-contrast]', 'aed-contrast');
  bind('data-font', 'button[data-font]', 'aed-font');

  // Menu główne na wąskich ekranach
  var toggler = document.querySelector('.navbar-toggler');
  var nav = document.getElementById('main-nav');
  if (toggler && nav) {
    toggler.addEventListener('click', function () {
      var open = toggler.getAttribute('aria-expanded') === 'true';
      toggler.setAttribute('aria-expanded', String(!open));
      toggler.textContent = open ? 'MENU' : 'ZAMKNIJ';
      nav.classList.toggle('show', !open);
    });
  }
})();
