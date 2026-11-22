import datetime, sys
from playwright.sync_api import sync_playwright
# Zrzuty prototypu do prezentacji (Playwright, Python).
# Serwery: cd app && python -m http.server 8765 (MAIN) oraz kopia app/ z rekordem wzorcowym
# (node presentation/narzedzia/rekord_wzorcowy.js <kopia-app>) na porcie 8766 (DEMO).
# Uruchomienie: python presentation/narzedzia/zrzuty.py [model citizen wcag desk]
# Zegar: wtorek 11:00, żeby „dostępny teraz” wyglądało jak w dzień.
import pathlib
OUT=str(pathlib.Path(__file__).resolve().parent.parent / "zrzuty-surowe") + "/"
pathlib.Path(OUT).mkdir(exist_ok=True)
MAIN="http://localhost:8765/"; DEMO="http://localhost:8766/"
T=datetime.datetime(2026,11,24,11,0)
IOS="Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"
MODEL="aed-warszawa-centrum-kultury-przykladowe-bd767fc6fc-mazowieckie"
def ctx(b,w,h,geo=None,mobile=False,perms=True):
    return b.new_context(viewport={"width":w,"height":h},device_scale_factor=2 if mobile else 1.5,is_mobile=mobile,has_touch=mobile,
        locale="pl-PL",timezone_id="Europe/Warsaw",geolocation=geo,permissions=["geolocation"] if (geo and perms) else [],user_agent=IOS if mobile else None)
def page(c):
    p=c.new_page(); p.clock.install(time=T); return p
KRK={"latitude":50.0614,"longitude":19.9372}
WAW={"latitude":52.2297,"longitude":21.0122}
which=sys.argv[1:] or ["all"]
want=lambda n:"all" in which or n in which
with sync_playwright() as pw:
    b=pw.chromium.launch()
    if want("model"):
        c=ctx(b,1440,900,WAW); p=page(c); p.goto(DEMO+"aed.html?aed="+MODEL); p.wait_for_timeout(1500)
        btn=p.get_by_role("button",name="Pokaż odległość")
        if btn.count(): btn.first.click()
        p.wait_for_timeout(7000); p.evaluate("window.scrollTo(0,0)"); p.wait_for_timeout(300)
        p.screenshot(path=OUT+"model-desktop.png"); 
        p.screenshot(path=OUT+"model-desktop-full.png",full_page=True); c.close()
        c=ctx(b,390,844,WAW,True); p=page(c); p.goto(DEMO+"aed.html?aed="+MODEL); p.wait_for_timeout(1500)
        btn=p.get_by_role("button",name="Pokaż odległość")
        if btn.count(): btn.first.click()
        p.wait_for_timeout(7000); p.evaluate("window.scrollTo(0,0)"); p.wait_for_timeout(300)
        p.screenshot(path=OUT+"model-mobile.png"); p.screenshot(path=OUT+"model-mobile-full.png",full_page=True); c.close()
    if want("citizen"):
        c=ctx(b,390,844,KRK,True); p=page(c); p.goto(MAIN+"index.html"); p.wait_for_timeout(2000)
        p.screenshot(path=OUT+"c1-start.png")
        p.click("#locate"); p.wait_for_timeout(9000)
        p.locator("#highlight").scroll_into_view_if_needed(); p.wait_for_timeout(500)
        p.screenshot(path=OUT+"c2-wynik.png")
        p.locator("#highlight [data-show]").first.click(); p.wait_for_timeout(6000)
        p.screenshot(path=OUT+"c3-dymek.png")
        p.locator(".popup-details-link").first.click(); p.wait_for_timeout(2500)
        btn=p.get_by_role("button",name="Pokaż odległość")
        if btn.count(): btn.first.click()
        p.wait_for_timeout(6000); p.evaluate("window.scrollTo(0,0)"); p.wait_for_timeout(300)
        p.screenshot(path=OUT+"c4-szczegoly.png"); c.close()
    if want("wcag"):
        c=ctx(b,390,844,KRK,True); p=page(c); p.goto(MAIN+"index.html"); p.wait_for_timeout(1500)
        p.click("button[data-contrast='black-yellow']"); p.click("#locate"); p.wait_for_timeout(8000); p.evaluate("window.scrollTo(0,0)")
        p.screenshot(path=OUT+"w-kontrast.png"); c.close()
        c=ctx(b,320,700,KRK,True); p=page(c); p.goto(MAIN+"index.html"); p.wait_for_timeout(1500)
        p.screenshot(path=OUT+"w-320.png"); print("scrollW",p.evaluate("document.documentElement.scrollWidth")); c.close()
        c=ctx(b,1440,900,KRK); p=page(c); p.goto(MAIN+"index.html"); p.wait_for_timeout(1500)
        p.click("button[data-font='200']")
        p.wait_for_timeout(500); p.screenshot(path=OUT+"w-tekst.png"); c.close()
        c=ctx(b,390,844,KRK,True,perms=False); p=page(c); p.goto(MAIN+"index.html"); p.wait_for_timeout(1500)
        p.click("#locate"); p.wait_for_timeout(1500); p.locator("#geo-help").scroll_into_view_if_needed()
        p.screenshot(path=OUT+"w-pomoc.png"); c.close()
        c=ctx(b,390,844,None,True); p=page(c); p.goto(MAIN+"index.html"); p.wait_for_timeout(1500)
        p.click("#search"); p.keyboard.type("krosno akademia",delay=60); p.wait_for_timeout(1200)
        p.screenshot(path=OUT+"w-podpowiedzi.png"); c.close()
    if want("desk"):
        c=ctx(b,1440,900,KRK); p=page(c); p.goto(MAIN+"index.html"); p.wait_for_timeout(1500)
        p.click("#locate"); p.wait_for_timeout(8000)
        p.locator("#highlight [data-show]").first.click(); p.wait_for_timeout(6000)
        p.evaluate("window.scrollTo(0,0)"); p.wait_for_timeout(300)
        p.screenshot(path=OUT+"desk-krakow.png"); c.close()
    b.close()
