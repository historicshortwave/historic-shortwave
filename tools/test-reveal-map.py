#!/usr/bin/env python3
"""Browser checks for the Reveal Station map (plan phase 6).

  python3 tools/test-reveal-map.py --chrome PATH [--width PX] [--shots DIR]
External hosts are blocked; recordings end in the normal playback-unavailable state.

New 3D receiver (HR64_APP=release/heritage-hr64-face; updated 2026-11-20 at Bill's request): the release ships
band-60m.json in place of full-inventory.json, and 49M-0173 (used for the unrevealed-clip check) is not in the
release, so that check uses the first 49 m release recording this test has not revealed.
"""
import functools, http.server, json, socketserver, sys, threading
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
APP = Path(__import__("os").environ["HR64_APP"]).resolve() if __import__("os").environ.get("HR64_APP") else ROOT / "app" / "heritage-h60"
args = sys.argv[1:]
opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
chrome, width, shots = opt("--chrome"), int(opt("--width", 1280)), opt("--shots")
FACE = (APP / "face.js").exists()   # the new 3D receiver (release/heritage-hr64-face)
SIDE = json.loads((APP / "geo" / "reveal-geography.json").read_text())["entries"]
RECS = {}
for f in ["band-60m.json" if FACE else "full-inventory.json", "band-90m.json", "band-49m.json"]:
    for r in json.loads((APP / f).read_text())["recordings"]: RECS[r["id"]] = r
if FACE:   # the release geography file leaves out the band; take it from the band file each recording is in
    for f in ("band-60m.json", "band-90m.json", "band-49m.json"):
        for r in json.loads((APP / f).read_text())["recordings"]:
            if r["id"] in SIDE: SIDE[r["id"]]["band"] = f[5:8]


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass


httpd = socketserver.TCPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(APP)))
threading.Thread(target=httpd.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{httpd.server_address[1]}"
failures = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  -> {detail}"))
    if not cond: failures.append(name)


def rid(band, inv):
    return next(k for k, e in SIDE.items() if e["band"] == band and str(e["inventoryId"]) == str(inv))


GOTO = """async ([band, id, hz]) => {
  const wait = ms => new Promise(r => setTimeout(r, ms));
  if (state.band !== band) { selectBand(band); for (let i = 0; i < 60 && state.band !== band; i++) await wait(50); }
  if (band === '60m' && state.mode !== 'full') { const s = document.getElementById('catalog-select'); s.value = 'full'; s.dispatchEvent(new Event('change')); for (let i = 0; i < 60 && state.mode !== 'full'; i++) await wait(50); }
  tune(hz); await wait(50);
  const sel = document.getElementById('recording-select');
  if (state.selected?.id !== id) { sel.value = id; sel.dispatchEvent(new Event('change')); await wait(50); }
  return state.selected?.id;
}"""
MAP = """() => { const m = document.querySelector('#reveal-panel .reveal-map'); if (!m) return null;
  return { state: m.dataset.state, record: m.dataset.record, highlight: m.dataset.highlight, animated: m.dataset.animated,
    ring: !!m.querySelector('[data-testid=map-ring]'), hl: (m.querySelector('[data-testid=map-highlight]')?.getAttribute('d') || '').length,
    text: m.innerText.replace(/\\s+/g, ' ').trim(), label: m.querySelector('svg')?.getAttribute('aria-label') }; }"""

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=chrome)
    ctx = browser.new_context(viewport={"width": width, "height": 900}, reduced_motion="reduce")
    page = ctx.new_page()
    errors, geo_requests, block = [], [], {"geo": False, "delay": 0}
    page.on("pageerror", lambda e: errors.append(str(e)))
    def route(r):
        url = r.request.url
        if not url.startswith(BASE): return r.abort()
        if "/geo/" in url or ("/vendor/" in url and "/vendor/fonts/" not in url):
            geo_requests.append(url.rsplit("/", 1)[-1])
            if block["geo"]: return r.abort()
            if block["delay"]: page.wait_for_timeout(block["delay"])
        return r.continue_()
    page.route("**/*", route)
    page.goto(BASE + "/index.html"); page.wait_for_timeout(600)
    m = lambda: page.evaluate(MAP)
    def reveal(): page.evaluate("document.getElementById('reveal-button').click()")
    def go(band, inv):
        k = rid(band, inv); got = page.evaluate(GOTO, [band, k, RECS[k]["frequencyHz"]]); return k, got

    # Blind until reveal: no geography or map library requests while tuning, playing and switching bands.
    page.click("#power-button"); page.wait_for_timeout(300)
    go("90m", "90M-0136"); go("49m", "49M-0296"); go("60m", 10); page.wait_for_timeout(300)
    page.click("#power-button")
    check("no map requests before the first reveal", geo_requests == [], geo_requests)
    check("no map card before reveal", m() is None)

    # Failure: the reveal text stays, the card says so, and the next reveal retries.
    block["geo"] = True
    reveal(); page.wait_for_timeout(600)
    st = m(); title = page.text_content("#reveal-panel h3")
    check("failed map download leaves reveal text intact", st and st["state"] == "error" and "Map unavailable" in st["text"] and "Cabinda" in title, (st, title))
    block["geo"] = False
    go("90m", "90M-0136"); reveal(); page.wait_for_timeout(1500)
    st = m()
    check("next reveal retries and draws", st and st["state"] == "drawn", st)
    check("Rhodesia 1979: period caption", st and st["text"].startswith("Zimbabwe Rhodesia") and "Borders as of 14 August 1979" in st["text"], st)
    check("CShapes attribution on the card (modified, licensed)", st and "Borders: CShapes 2.0 (Schvitz et al.), simplified, CC BY-NC-SA 4.0 · Map credits" in st["text"], st)
    links = page.evaluate("[...document.querySelectorAll('#reveal-panel .map-credit a')].map(a => [a.textContent, a.href, a.target, a.rel])")
    check("card links to CShapes and the license (new tab, noopener)", links[:2] == [
        ["CShapes 2.0", "https://icr.ethz.ch/data/cshapes/", "_blank", "noopener noreferrer"],
        ["CC BY-NC-SA 4.0", "https://creativecommons.org/licenses/by-nc-sa/4.0/", "_blank", "noopener noreferrer"]], links)
    page.click("[data-testid=button-map-credits]"); page.wait_for_timeout(300)
    credits = page.evaluate("""(() => { const d = document.getElementById('about-dialog'), c = document.getElementById('map-credits');
      const r = c.getBoundingClientRect(), dr = d.getBoundingClientRect();
      return { open: d.open, inView: r.top >= dr.top - 1 && r.top < dr.bottom, text: c.innerText + ' ' + c.nextElementSibling.innerText }; })()""")
    check("Map credits opens Field notes at the credits", credits["open"] and credits["inView"], credits)
    check("Field notes: citation, license and modification note", all(t in credits["text"] for t in [
        "Mapping The International System, 1886-2017: The CShapes 2.0 Dataset", "Journal of Conflict Resolution 66(1): 144–61",
        "CC BY-NC-SA 4.0", "Changes made for this receiver", "simplified", "same CC BY-NC-SA 4.0 license", "Natural Earth"]), credits["text"])
    page.keyboard.press("Escape"); page.wait_for_timeout(150)
    check("reduced motion: drawn without animation", st and st["animated"] == "no", st)
    check("svg has an accessible label", st and st["label"] == "Map highlighting Zimbabwe Rhodesia", st)

    # Tuning inside the capture window keeps the same map node (no redraw).
    page.evaluate("window.__mapNode = document.querySelector('#reveal-panel .reveal-map')")
    page.evaluate("tune(state.hz + 300)"); page.wait_for_timeout(150)
    same = page.evaluate("document.querySelector('#reveal-panel .reveal-map') === window.__mapNode")
    check("tuning within the recording keeps the map (no redraw)", same)
    page.evaluate("tune(state.hz - 300)")

    cases = [
        ("49m", "49M-0296", lambda s: s["text"].startswith("Latvian SSR · shown as present-day Latvia") and not s["ring"]),
        ("49m", "49M-0058", lambda s: s["text"].startswith("Uzbek SSR · shown as present-day Uzbekistan")),
        ("49m", "49M-0072", lambda s: s["text"].startswith("USSR (republic not established)") and "Transmitter: possibly the Moscow area" in s["text"]),
        ("60m", 63, lambda s: s["text"].startswith("Karelian ASSR (Russian SFSR)")),
        ("49m", "49M-0328", lambda s: s["text"].startswith("Vatican City") and s["ring"] and "Area: Made with Natural Earth" in s["text"]),
        ("49m", "49M-0248", lambda s: s["text"].startswith("Bonaire (Netherlands Antilles") and s["ring"] and "Transmitter: Bonaire relay" in s["text"]),
        ("49m", "49M-0042", lambda s: s["text"].startswith("Antigua (Antigua and Barbuda)") and s["ring"]),
        ("49m", "49M-0220", lambda s: "Biafra" in s["text"] and "approximate area" in s["text"] and "8 September 1969" in s["text"]),
        ("90m", "90M-0066", lambda s: s["text"].startswith("East Timor, under Indonesian administration") and "shown as present-day Timor-Leste" in s["text"]),
        ("60m", 10, lambda s: s["text"].startswith("Angola") and "recording date: 1970s, timing unknown" in s["text"] and "Recordist:" not in s["text"]),
    ]
    for band, inv, ok in cases:
        k, got = go(band, inv)
        if not page.evaluate(f"state.revealed.has('{k}')"): reveal()
        page.wait_for_timeout(500)
        st = m()
        good = got == k and st and st["state"] == "drawn" and st["record"] == k and st["hl"] > 20 and ok(st)
        check(f"{band} {inv}: {st['text'][:70] if st else None}", good, st)
        if shots: page.locator("#reveal-panel").screenshot(path=f"{shots}/map-{inv}.png")

    k, _ = go("49m", "49M-0026"); reveal(); page.wait_for_timeout(300)
    st = m(); check("clandestine: no highlight, says not established", st and st["state"] == "none" and "Transmitter country not established" in st["text"] and st["hl"] == 0, st)

    # Changing clips hides the map for an unrevealed recording.
    unrevealed = "49M-0173"
    if FACE:
        unrevealed = next(e["inventoryId"] for k, e in SIDE.items() if e["band"] == "49m" and k in RECS and not page.evaluate(f"state.revealed.has('{k}')"))
    go("49m", unrevealed); page.wait_for_timeout(200)
    check("unrevealed clip shows no map", m() is None and page.is_hidden("#reveal-panel"))

    # Stale guard: a slow map for clip A must not land after switching to revealed clip B.
    page.evaluate("window.RevealMap.clear()")
    ctx2 = browser.new_context(viewport={"width": width, "height": 900})
    p2 = ctx2.new_page(); slow = {"on": True}
    def route2(r):
        url = r.request.url
        if not url.startswith(BASE): return r.abort()
        if "reveal-geography.json" in url and slow["on"]: p2.wait_for_timeout(1200)
        return r.continue_()
    p2.route("**/*", route2); p2.goto(BASE + "/index.html"); p2.wait_for_timeout(600)
    kA = rid("90m", "90M-0136"); kB = rid("49m", "49M-0296")
    p2.evaluate(GOTO, ["90m", kA, RECS[kA]["frequencyHz"]]); p2.evaluate("document.getElementById('reveal-button').click()")
    p2.wait_for_timeout(100)
    p2.evaluate(GOTO, ["49m", kB, RECS[kB]["frequencyHz"]]); p2.evaluate("document.getElementById('reveal-button').click()")
    p2.wait_for_timeout(2500)
    st = p2.evaluate(MAP); n = p2.evaluate("document.querySelectorAll('.reveal-map').length")
    check("late map for an earlier clip is discarded", st and st["record"] == kB and st["state"] == "drawn" and st["text"].startswith("Latvian SSR") and n == 1, (st, n))
    check("animation used when motion is allowed", st and st["animated"] == "yes", st)
    ctx2.close()

    check("no page errors", not errors, errors)
    browser.close()
httpd.shutdown()
print(f"{'ALL PASSED' if not failures else str(len(failures)) + ' FAILED'} at {width}px")
sys.exit(1 if failures else 0)
