// Kontrast par kolorów tekst/tło używanych w style.css – WCAG 2.2 AA (≥ 4,5:1 dla tekstu,
// ≥ 3:1 dla elementów graficznych i obramowań kontrolek). Uruchomienie: node --test app/tests/*.test.js
'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const css = fs.readFileSync(path.join(__dirname, '..', 'css', 'style.css'), 'utf-8');
const vars = Object.fromEntries([...css.matchAll(/--([a-z-]+):\s*(#[0-9a-f]{6})/gi)].map((m) => [m[1], m[2]]));

function luminance(hex) {
  const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  const l = c.map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return 0.2126 * l[0] + 0.7152 * l[1] + 0.0722 * l[2];
}
function contrast(a, b) {
  const [x, y] = [luminance(a), luminance(b)].sort((p, q) => q - p);
  return (x + 0.05) / (y + 0.05);
}
const v = (name) => {
  assert.ok(vars[name], `brak zmiennej --${name}`);
  return vars[name];
};

const TEXT_PAIRS = [
  ['text na białym', v('text'), '#ffffff'],
  ['nagłówki na białym', v('heading'), '#ffffff'],
  ['tekst na jasnym tle', v('text'), v('bg-light')],
  ['link / przycisk obrys', v('primary'), '#ffffff'],
  ['biały na przycisku', '#ffffff', v('primary')],
  ['biały na przycisku (hover)', '#ffffff', v('primary-hover')],
  ['biały na granatowym pasku', '#ffffff', v('navy')],
  ['przycisk obrysowy hover', v('primary'), v('highlight')],
  ['komunikat', v('heading'), v('highlight')],
  ['odznaka dostępny', v('ok-fg'), v('ok-bg')],
  ['odznaka nieznany', v('unknown-fg'), v('unknown-bg')],
  ['odznaka niedostępny', v('closed-fg'), v('closed-bg')],
  ['odznaka przykład / ostrzeżenie', v('example-fg'), v('example-bg')],
  ['wskazówka (muted)', v('muted'), v('bg-light')],
  ['link 112', '#a1002f', '#ffffff'],
  ['link 112 hover', '#a1002f', '#fdeef2'],
];

for (const [name, fg, bg] of TEXT_PAIRS) {
  test(`kontrast tekstu: ${name} (${fg} na ${bg}) ≥ 4,5`, () => {
    assert.ok(contrast(fg, bg) >= 4.5, contrast(fg, bg).toFixed(2));
  });
}

const GRAPHIC_PAIRS = [
  ['pinezka dostępny', v('ok-pin'), '#ffffff'],
  ['pinezka nieznany', v('unknown-pin'), '#ffffff'],
  ['pinezka niedostępny', v('closed-pin'), '#ffffff'],
  ['pinezka przykład', v('example-pin'), '#ffffff'],
  ['obrys pola wyboru', '#767676', '#ffffff'],
];
for (const [name, fg, bg] of GRAPHIC_PAIRS) {
  test(`kontrast grafiki: ${name} ≥ 3`, () => {
    assert.ok(contrast(fg, bg) >= 3, contrast(fg, bg).toFixed(2));
  });
}
