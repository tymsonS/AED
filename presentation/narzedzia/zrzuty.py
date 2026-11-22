import datetime, sys
from playwright.sync_api import sync_playwright
# Zrzuty ekranu prototypu do prezentacji (Playwright, Python).
# Uruchom serwer: cd app && python -m http.server 8765, potem: python presentation/narzedzia/zrzuty.py [desk mob verified detail suggest geohelp hc w320 start]
# Zegar ustawiony na wtorek 11:00, żeby „dostępny teraz” wyglądało jak w dzień.
import pathlib
OUT=str(pathlib.Path(__file__).resolve().parent.parent / "zrzuty-surowe") + "/"
pathlib.Path(OUT).mkdir(exist_ok=True)
BASE="http://localhost:8765/"
T=datetime.datetime(2026,11,24,11,0)
def ctx(b, w, h, geo=None, mobile=False, perms=True):
    c=b.new_context(viewport={"width":w,"height":h}, device_scale_factor=2 if mobile else 1.5,
        is_mobile=mobile, has_touch=mobile, locale="pl-PL", timezone_id="Europe/Warsaw",
        geolocation=geo, permissions=["geolocation"] if (geo and perms) else [],
        user_agent=("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1" if mobile else None))
    return c
def page(c):
    p=c.new_page(); p.clock.install(time=T); return p
def wait_routes(p, ms=9000):
    p.wait_for_timeout(ms)
with sync_playwright() as pw:
    b=pw.chromium.launch()
    which=sys.argv[1:] or ["all"]
    def want(n): return "all" in which or n in which
    KRK={"latitude":50.0614,"longitude":19.9372}
    KRO={"latitude":49.6889,"longitude":21.7693}
    if want("desk"):
        c=ctx(b,1440,900,KRK); p=page(c); p.goto(BASE+"index.html"); p.wait_for_timeout(1500)
        p.click("#locate"); wait_routes(p)
        p.click("#highlight [data-show]") if p.locator("#highlight [data-show]").count() else None
        wait_routes(p,6000)
        p.evaluate("window.scrollTo(0,0)"); p.wait_for_timeout(400)
        p.screenshot(path=OUT+"01-desktop-krakow.png"); c.close()
    if want("start"):
        c=ctx(b,1440,900); p=page(c); p.goto(BASE+"index.html"); p.wait_for_timeout(2500)
        p.screenshot(path=OUT+"00-desktop-start.png"); c.close()
    if want("mob"):
        c=ctx(b,390,844,KRK,True); p=page(c); p.goto(BASE+"index.html"); p.wait_for_timeout(1500)
        p.click("#locate"); wait_routes(p)
        p.locator("#highlight").scroll_into_view_if_needed(); p.wait_for_timeout(500)
        p.screenshot(path=OUT+"02-mobile-wynik.png")
        p.locator("#highlight [data-show]").first.click(); wait_routes(p,6000)
        p.screenshot(path=OUT+"03-mobile-dymek.png"); c.close()
    if want("verified"):
        c=ctx(b,1440,900,KRO); p=page(c); p.goto(BASE+"index.html"); p.wait_for_timeout(1500)
        p.click("#locate"); wait_routes(p,4000)
        p.goto(BASE+"index.html?aed=aed-krosno-panstwowa-akademia-nauk-stosowanych-b1be591660-podkarpackie"); wait_routes(p,8000)
        p.evaluate("window.scrollTo(0,0)"); p.wait_for_timeout(400)
        p.screenshot(path=OUT+"04-desktop-zweryfikowany.png"); c.close()
    if want("detail"):
        for name,w,h,mob in (("05-szczegoly-desktop",1440,900,False),("06-szczegoly-mobile",390,844,True)):
            c=ctx(b,w,h,KRO,mob); p=page(c)
            p.goto(BASE+"aed.html?aed=aed-krosno-panstwowa-akademia-nauk-stosowanych-b1be591660-podkarpackie"); p.wait_for_timeout(1500)
            btn=p.get_by_role("button", name="Pokaż odległość")
            if btn.count(): btn.first.click(); wait_routes(p,6000)
            p.evaluate("window.scrollTo(0,0)"); p.wait_for_timeout(300); p.screenshot(path=OUT+name+".png"); c.close()
    if want("suggest"):
        c=ctx(b,390,844,None,True); p=page(c); p.goto(BASE+"index.html"); p.wait_for_timeout(1500)
        p.click("#search"); p.keyboard.type("krosno akademia", delay=60); p.wait_for_timeout(1200)
        p.screenshot(path=OUT+"07-mobile-podpowiedzi.png"); c.close()
    if want("geohelp"):
        c=ctx(b,390,844,KRK,True,perms=False); p=page(c); p.goto(BASE+"index.html"); p.wait_for_timeout(1500)
        p.click("#locate"); p.wait_for_timeout(1500)
        p.locator("#geo-help").scroll_into_view_if_needed()
        p.screenshot(path=OUT+"08-mobile-pomoc-lokalizacja.png"); c.close()
    if want("hc"):
        c=ctx(b,390,844,KRK,True); p=page(c); p.goto(BASE+"index.html"); p.wait_for_timeout(1500)
        p.click("button[data-contrast='black-yellow']"); p.click("button[data-font='150']") if False else None
        p.click("#locate"); wait_routes(p)
        p.screenshot(path=OUT+"09-mobile-kontrast.png"); c.close()
    if want("w320"):
        c=ctx(b,320,700,KRK,True); p=page(c); p.goto(BASE+"index.html"); p.wait_for_timeout(1500)
        p.click("#locate"); wait_routes(p,6000); p.evaluate("window.scrollTo(0,0)"); p.wait_for_timeout(300)
        p.screenshot(path=OUT+"10-320px.png"); print("scrollW 320:",p.evaluate("document.documentElement.scrollWidth")); c.close()
    b.close()
