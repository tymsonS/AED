import datetime, sys
from playwright.sync_api import sync_playwright
# Zrzuty prototypu do prezentacji (Playwright, Python), na kopii app/ z rekordem wzorcowym:
#   cp -r app /tmp/app-demo && node presentation/narzedzia/rekord_wzorcowy.js /tmp/app-demo
#   cd /tmp/app-demo && python -m http.server 8766
# Uruchomienie: python presentation/narzedzia/zrzuty.py [flow hc font desk]
# Zegar: wtorek 11:00; start 52.176, 21.016 (ok. 220 m od AED wzorcowego przy Al. Lotników 16).
# Krok 4 ścieżki obywatela (trasa) to zrzut Map Google otwartych przyciskiem „Wyznacz trasę”.
import pathlib
OUT=str(pathlib.Path(__file__).resolve().parent.parent / "zrzuty-surowe") + "/"
pathlib.Path(OUT).mkdir(exist_ok=True)
DEMO="http://localhost:8766/"
T=datetime.datetime(2026,11,24,11,0)
IOS="Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"
MODEL="aed-warszawa-centrum-kultury-przykladowe-bd767fc6fc-mazowieckie"
GEO={"latitude":52.176,"longitude":21.016}
def ctx(b,w,h,mobile=True,geo=GEO):
    return b.new_context(viewport={"width":w,"height":h},device_scale_factor=2,is_mobile=mobile,has_touch=mobile,locale="pl-PL",timezone_id="Europe/Warsaw",geolocation=geo,permissions=["geolocation"],user_agent=IOS if mobile else None)
which=sys.argv[1:] or ["all"]; want=lambda n:"all" in which or n in which
with sync_playwright() as pw:
    b=pw.chromium.launch()
    if want("flow"):
        c=ctx(b,390,844); p=c.new_page(); p.clock.install(time=T)
        p.goto(DEMO+"index.html"); p.wait_for_timeout(1800); p.screenshot(path=OUT+"o1-start.png")
        p.click("#locate"); p.wait_for_timeout(9000)
        print("najblizszy:", p.locator("#highlight h3, #highlight .highlight-title").first.inner_text() if p.locator("#highlight h3, #highlight .highlight-title").count() else p.locator("#highlight").inner_text()[:120])
        # tytułowy: mapa u góry, pod nią karta najbliższego AED
        top=p.evaluate("document.querySelector('#map').getBoundingClientRect().top+window.scrollY")
        hb=p.evaluate("(()=>{const r=document.querySelector('#highlight').getBoundingClientRect();return r.bottom+window.scrollY})()")
        print("map top",top,"highlight bottom",hb)
        p.evaluate(f"window.scrollTo(0,{max(0,hb-844+16)})"); p.wait_for_timeout(600)
        p.screenshot(path=OUT+"o2-wynik.png")
        p.locator("#highlight [data-show]").first.click(); p.wait_for_timeout(5000)
        p.screenshot(path=OUT+"o3-dymek.png")
        p.goto(DEMO+"aed.html?aed="+MODEL); p.wait_for_timeout(1500)
        btn=p.get_by_role("button",name="Pokaż odległość")
        if btn.count(): btn.first.click()
        p.wait_for_timeout(6000); p.evaluate("window.scrollTo(0,0)"); p.wait_for_timeout(300)
        p.screenshot(path=OUT+"o4-szczegoly.png"); p.screenshot(path=OUT+"o4-full.png",full_page=True); c.close()
    if want("desk"):
        c=ctx(b,1440,900,mobile=False); p=c.new_page(); p.clock.install(time=T)
        p.goto(DEMO+"aed.html?aed="+MODEL); p.wait_for_timeout(1500)
        btn=p.get_by_role("button",name="Pokaż odległość")
        if btn.count(): btn.first.click()
        p.wait_for_timeout(7000); p.evaluate("window.scrollTo(0,0)"); p.wait_for_timeout(300)
        p.screenshot(path=OUT+"model-desktop.png"); p.screenshot(path=OUT+"model-desktop-full.png",full_page=True); c.close()
    if want("hc"):
        c=ctx(b,390,844); p=c.new_page(); p.clock.install(time=T)
        p.goto(DEMO+"index.html"); p.wait_for_timeout(1500)
        p.click("button[data-contrast='black-yellow']"); p.click("#locate"); p.wait_for_timeout(9000)
        hb=p.evaluate("(()=>{const r=document.querySelector('#highlight').getBoundingClientRect();return r.bottom+window.scrollY})()")
        p.evaluate(f"window.scrollTo(0,{max(0,hb-844+16)})"); p.wait_for_timeout(600)
        p.screenshot(path=OUT+"w-kontrast.png"); c.close()
    if want("font"):
        c=ctx(b,768,1024,mobile=False); p=c.new_page(); p.clock.install(time=T)
        p.goto(DEMO+"index.html"); p.wait_for_timeout(1500)
        p.click("button[data-font='200']"); p.wait_for_timeout(800)
        p.screenshot(path=OUT+"w-tekst200.png"); c.close()
    b.close()
