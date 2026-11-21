// index.html: każdy lokalny CSS/JS z tym samym numerem wersji (?v=…), żeby przeglądarka
// nie łączyła nowego HTML ze starymi plikami z pamięci podręcznej. node --test app/tests/*.test.js
'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

// Obie strony: wyszukiwarka i podstrona AED („Szczegóły”).
const pages = ['index.html', 'aed.html'];
const refs = pages.flatMap((p) => {
  const html = fs.readFileSync(path.join(__dirname, '..', p), 'utf-8');
  return [...html.matchAll(/(?:href|src)="((?:css|js|data|vendor)\/[^"]+)"/g)].map((m) => m[1]);
});

test('wszystkie lokalne CSS/JS mają ten sam parametr wersji', () => {
  const assets = refs.filter((r) => /\.(css|js)(\?|$)/.test(r));
  assert.ok(assets.length >= 7, String(assets.length));
  const versions = new Set(assets.map((r) => (r.match(/\?v=([\w-]+)$/) || [])[1]));
  assert.equal(versions.size, 1, JSON.stringify(assets));
  assert.ok([...versions][0], "brak ?v= w odnośnikach");
});

test('pliki z index.html i aed.html istnieją', () => {
  for (const r of refs) {
    const file = path.join(__dirname, '..', r.split('?')[0]);
    assert.ok(fs.existsSync(file), r);
  }
});
