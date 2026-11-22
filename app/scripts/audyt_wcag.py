import json, datetime, sys
from playwright.sync_api import sync_playwright
"""Audyt WCAG 2.2 AA prototypu narzędziem axe-core (Playwright, Python).

Uruchomienie (z głównego katalogu repozytorium):
  npm i --prefix /tmp/axe axe-core@4            # axe-core poza repozytorium
  cd app && python -m http.server 8765 &        # serwer prototypu
  python app/scripts/audyt_wcag.py /tmp/axe/node_modules/axe-core/axe.min.js

Sprawdza stronę główną (start, po lokalizacji, z dymkiem, trzy tryby kontrastu) i podstronę AED,
na komputerze i telefonie. Wynik: wypisuje naruszenia i zapisuje JSON obok skryptu.
"""
import pathlib
AXE=open(sys.argv[1]).read()
BASE="http://localhost:8765/"
SLUG="aed-krosno-panstwowa-akademia-nauk-stosowanych-b1be591660-podkarpackie"
T=datetime.datetime(2026,11,24,11,0)
TAGS=["wcag2a","wcag2aa","wcag21a","wcag21aa","wcag22aa"]
res={}
def audit(name,pg):
    pg.add_script_tag(content=AXE)
    r=pg.evaluate("tags=>axe.run(document,{runOnly:{type:'tag',values:tags}})",TAGS)
    res[name]={"violations":[{"id":v["id"],"impact":v["impact"],"help":v["help"],"nodes":[n["target"] for n in v["nodes"]][:6],"count":len(v["nodes"])} for v in r["violations"]],"passes":len(r["passes"]),"incomplete":[i["id"] for i in r["incomplete"]]}
with sync_playwright() as p:
    b=p.chromium.launch()
    for dev,w,h,mob in (("komputer",1440,900,False),("telefon",390,844,True)):
        c=b.new_context(viewport={"width":w,"height":h},is_mobile=mob,has_touch=mob,locale="pl-PL",timezone_id="Europe/Warsaw",geolocation={"latitude":50.0614,"longitude":19.9372},permissions=["geolocation"])
        pg=c.new_page(); pg.clock.install(time=T)
        pg.goto(BASE+"index.html"); pg.wait_for_timeout(1500); audit(f"index start ({dev})",pg)
        pg.click("#locate"); pg.wait_for_timeout(8000); audit(f"index po lokalizacji ({dev})",pg)
        pg.locator("#highlight [data-show]").first.click(); pg.wait_for_timeout(4000); audit(f"index z dymkiem ({dev})",pg)
        for mode in ("black-white","black-yellow","yellow-black"):
            pg.click(f"button[data-contrast='{mode}']") if pg.locator(f"button[data-contrast='{mode}']").is_visible() else pg.evaluate(f"document.documentElement.setAttribute('data-contrast','{mode}')")
            pg.wait_for_timeout(400); audit(f"index kontrast {mode} ({dev})",pg)
        pg.evaluate("document.documentElement.removeAttribute('data-contrast')")
        pg.goto(BASE+"aed.html?aed="+SLUG); pg.wait_for_timeout(2500); audit(f"aed.html ({dev})",pg)
        c.close()
    b.close()
json.dump(res,open(pathlib.Path(__file__).with_name('audyt-wcag-wynik.json'),'w'),ensure_ascii=False,indent=1)
for k,v in res.items():
    print(k, "naruszenia:", [(x["id"],x["impact"],x["count"]) for x in v["violations"]], "passes",v["passes"], "incomplete", v["incomplete"])
