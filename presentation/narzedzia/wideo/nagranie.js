// Nagrywa ścieżkę obywatela w prototypie (telefon 390×844 @2x) jako klatki JPEG z czasami (CDP screencast).
// Opis i kolejność kroków: presentation/narzedzia/wideo/README.md.
// Użycie: node nagranie.js [katalog-roboczy]   (domyślnie /tmp/aedane-wideo), strona demo na http://localhost:8770/
let chromium;
try { ({ chromium } = require('playwright')); } catch (e) { ({ chromium } = require('/opt/node-tools/node_modules/playwright')); }
const fs = require('fs');
const OUT = (process.argv[2] || '/tmp/aedane-wideo') + '/rec';
const DEMO = 'http://localhost:8770/';
const MODEL = 'aed-warszawa-centrum-kultury-przykladowe-bd767fc6fc-mazowieckie';
const IOS = 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1';
const TAP_CSS = `.__tap{position:fixed;z-index:2147483647;width:56px;height:56px;margin:-28px 0 0 -28px;border-radius:50%;
  background:rgba(0,150,94,.35);border:3px solid rgba(0,150,94,.9);pointer-events:none;animation:__t .7s ease-out forwards}
  @keyframes __t{0%{transform:scale(.4);opacity:1}100%{transform:scale(1.3);opacity:0}}`;

(async () => {
  const b = await chromium.launch();
  const c = await b.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true,
    locale: 'pl-PL', timezoneId: 'Europe/Warsaw', geolocation: { latitude: 52.176, longitude: 21.016 },
    permissions: ['geolocation'], userAgent: IOS });
  await c.addInitScript((css) => {
    window.__tap = (x, y) => { const d = document.createElement('div'); d.className = '__tap'; d.style.left = x + 'px'; d.style.top = y + 'px';
      document.body.appendChild(d); setTimeout(() => d.remove(), 800); };
    document.addEventListener('DOMContentLoaded', () => { const s = document.createElement('style'); s.textContent = css; document.head.appendChild(s); });
  }, TAP_CSS);
  const p = await c.newPage();
  await p.clock.install({ time: new Date('2026-11-24T11:00:00+01:00') });
  const cdp = await c.newCDPSession(p);
  let scene = null, frames = [];
  cdp.on('Page.screencastFrame', async (f) => {
    try { await cdp.send('Page.screencastFrameAck', { sessionId: f.sessionId }); } catch (e) {}
    if (!scene) return;
    const n = frames.length; const file = `${OUT}/${scene}/${String(n).padStart(5, '0')}.jpg`;
    fs.writeFileSync(file, Buffer.from(f.data, 'base64')); frames.push([f.metadata.timestamp, file]);
  });
  async function start(name) {
    scene = name; frames = []; fs.rmSync(`${OUT}/${name}`, { recursive: true, force: true }); fs.mkdirSync(`${OUT}/${name}`, { recursive: true });
    await cdp.send('Page.startScreencast', { format: 'jpeg', quality: 92, maxWidth: 780, maxHeight: 1688, everyNthFrame: 1 });
    // wymuś pierwszą klatkę
    await p.evaluate(() => { document.body.style.outline = '0px solid transparent'; });
  }
  async function stop() {
    await p.waitForTimeout(150);
    await cdp.send('Page.stopScreencast');
    const end = Date.now() / 1000;
    fs.writeFileSync(`${OUT}/${scene}/frames.json`, JSON.stringify({ frames, end }));
    console.log(scene, frames.length, 'klatek', frames.length ? (end - frames[0][0]).toFixed(1) + ' s' : '');
    scene = null;
  }
  async function tap(loc) {
    await loc.scrollIntoViewIfNeeded();
    const bb = await loc.boundingBox();
    await p.evaluate(([x, y]) => window.__tap(x, y), [bb.x + bb.width / 2, bb.y + bb.height / 2]);
    await p.waitForTimeout(350);
    await loc.click();
  }
  async function smooth(y, ms) {
    await p.evaluate(([y, ms]) => new Promise((r) => {
      const y0 = window.scrollY, t0 = performance.now();
      function step(t) { const k = Math.min(1, (t - t0) / ms); const e = k < .5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
        window.scrollTo(0, y0 + (y - y0) * e); if (k < 1) requestAnimationFrame(step); else r(); }
      requestAnimationFrame(step);
    }), [y, ms]);
  }
  await p.goto(DEMO + 'index.html'); await p.waitForTimeout(2500);
  await p.clock.resume();

  // 1. Start
  await start('s1'); await p.waitForTimeout(2500); await stop();

  // 2. Lokalizacja → najbliższy AED (trasy liczą się kilka sekund – nagrywamy całość, przytniemy później)
  await start('s2');
  await tap(p.locator('#locate'));
  await p.waitForTimeout(9000);
  const hb = await p.evaluate(() => document.querySelector('#highlight').getBoundingClientRect().bottom + window.scrollY);
  await smooth(Math.max(0, hb - 844 + 16), 1400); await p.waitForTimeout(2500);
  await stop();

  // 3. Dymek na mapie ze zdjęciem
  await start('s3');
  await tap(p.locator('#highlight [data-show]').first());
  await p.waitForTimeout(5500);
  await stop();

  // 4. Podstrona AED z pełnymi danymi
  await start('s4');
  await p.goto(DEMO + 'aed.html?aed=' + MODEL);
  await p.waitForTimeout(1500);
  const btn = p.getByRole('button', { name: 'Pokaż odległość' });
  if (await btn.count()) await tap(btn.first());
  await p.waitForTimeout(4500);
  const H = await p.evaluate(() => document.documentElement.scrollHeight);
  const kd = await p.evaluate(() => { const h = [...document.querySelectorAll('h2')].find((e) => /Kiedy/.test(e.textContent)); return h ? h.getBoundingClientRect().top + window.scrollY - 20 : 900; });
  await smooth(kd, 2200); await p.waitForTimeout(2200);
  const wf = await p.evaluate(() => { const h = [...document.querySelectorAll('h2')].find((e) => /Weryfikacja/.test(e.textContent)); return h ? h.getBoundingClientRect().top + window.scrollY - 20 : 1800; });
  await smooth(Math.min(wf, H - 844), 2200); await p.waitForTimeout(2500);
  await stop();

  // 5. Legenda pod mapą
  await p.goto(DEMO + 'index.html'); await p.waitForTimeout(2500);
  await start('s5');
  const lg = await p.evaluate(() => { const r = document.querySelector('.legend-box').getBoundingClientRect(); return r.bottom + window.scrollY - 844 + 24; });
  await smooth(lg, 2400); await p.waitForTimeout(3500);
  await stop();

  // 6. Tryb wysokiego kontrastu
  await smooth(0, 1); await p.waitForTimeout(500);
  await start('s6');
  await p.waitForTimeout(800);
  await tap(p.locator("button[data-contrast='black-yellow']"));
  await p.waitForTimeout(1500);
  await tap(p.locator('#locate'));
  await p.waitForTimeout(7000);
  const hb2 = await p.evaluate(() => document.querySelector('#highlight').getBoundingClientRect().bottom + window.scrollY);
  await smooth(Math.max(0, hb2 - 844 + 16), 1400); await p.waitForTimeout(2500);
  await stop();

  await b.close();
})();
